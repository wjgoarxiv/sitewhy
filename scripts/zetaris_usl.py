"""Build the SiteWhy Unified Semantic Layer (USL) on the local Zetaris instance.

Registers >=3 sources (moratoria, state legislation, curated rules, county
sources), runs exploratory queries per source, materializes one USL join table
(``usl_site_screen``), runs USL + data-quality queries, and saves every output
under ``zetaris/evidence/`` plus the DDL in ``zetaris/usl.sql``.

Connection settings come from the environment only (``ZETARIS_BASE_URL``,
``ZETARIS_ORG_ID``, ``ZETARIS_API_KEY``) -- source ``~/.hackathon-keys.env``
in the same shell command before running. Values are never printed or saved.

Local Zetaris note: the SQL-editor proxy rejects the ``X-Request-ID`` header
(HTTP 400), so this script omits it. Writes go through ``CREATE LIGHTNING
FILESTORE TABLE`` (persistent); plain Spark ``CREATE VIEW``/CTAS statements do
not survive across proxy requests, so the USL is a materialized join table and
``zetaris/usl.sql`` records the exact build query alongside the DDL.

Usage:
    set -a; . ~/.hackathon-keys.env; set +a
    uv run python scripts/zetaris_usl.py [--offline]
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_SEED = ROOT / "data" / "seed"
MORATORIA_CSV = DATA_SEED / "moratorium_nation" / "moratorium_inventory.csv"
LEGISLATION_CSV = DATA_SEED / "moratorium_nation" / "state_legislation.csv"
RULES_YAML = ROOT / "data" / "layers" / "rules.yaml"
COUNTY_YAML = ROOT / "data" / "layers" / "county_sources.yaml"
RULES_CSV = DATA_SEED / "curated_rules.csv"
SOURCES_CSV = DATA_SEED / "county_sources.csv"
USL_CSV = DATA_SEED / "usl_site_screen.csv"

ZETARIS_DIR = ROOT / "zetaris"
EVIDENCE_DIR = ZETARIS_DIR / "evidence"
USL_SQL_PATH = ZETARIS_DIR / "usl.sql"

SCHEMA = "SITEWHY"
CONTAINER_DIR = "/home/zetaris/customer-data/shared/sitewhy"
DOCKER_CANDIDATES = [
    "/Applications/Docker.app/Contents/Resources/bin/docker",
    shutil.which("docker") or "",
    str(Path.home() / ".docker/bin/docker"),
]

RULES_COLUMNS = [
    "rule_id", "layer", "title", "scope_iso", "mw_threshold", "mw_inclusive",
    "check_label", "quote", "source_url", "source_title", "as_of", "status",
]
SOURCES_COLUMNS = ["moratorium_id", "url", "title"]
USL_COLUMNS = [
    "moratorium_id", "state", "state_abbrev", "jurisdiction", "jurisdiction_type",
    "enacted_status", "current_end_date_iso", "state_bill_count",
    "state_bills_enacted", "federal_rules", "state_rules", "county_source_count",
    "county_source_titles",
]

# (name, sql) per source; every query runs against local Zetaris.
EXPLORATORY = {
    "moratoria": [
        ("counts_by_status",
         "SELECT enacted_status, COUNT(*) AS n FROM SITEWHY.moratoria "
         "GROUP BY enacted_status ORDER BY n DESC"),
        ("top_active_states",
         "SELECT state_abbrev, COUNT(*) AS n FROM SITEWHY.moratoria "
         "WHERE enacted_status IN ('active', 'extended') "
         "GROUP BY state_abbrev ORDER BY n DESC LIMIT 10"),
        ("washington_county_md",
         "SELECT moratorium_id, jurisdiction, enacted_status, current_end_date_iso "
         "FROM SITEWHY.moratoria WHERE moratorium_id LIKE 'md-washington%'"),
    ],
    "state_legislation": [
        ("counts_by_bill_status",
         "SELECT bill_status_category, COUNT(*) AS n FROM SITEWHY.state_legislation "
         "GROUP BY bill_status_category ORDER BY n DESC"),
        ("texas_bills",
         "SELECT bill, bill_status_category, last_action_date_iso "
         "FROM SITEWHY.state_legislation WHERE state_abbrev = 'TX' ORDER BY bill"),
        ("enacted_by_state",
         "SELECT state_abbrev, COUNT(*) AS n FROM SITEWHY.state_legislation "
         "WHERE bill_status_category = 'enacted' "
         "GROUP BY state_abbrev ORDER BY n DESC LIMIT 10"),
    ],
    "curated_rules": [
        ("counts_by_layer",
         "SELECT layer, COUNT(*) AS n FROM SITEWHY.curated_rules "
         "GROUP BY layer ORDER BY n DESC"),
        ("all_rules",
         "SELECT rule_id, layer, title FROM SITEWHY.curated_rules ORDER BY rule_id"),
        ("ercot_scoped_rules",
         "SELECT rule_id, title, mw_threshold FROM SITEWHY.curated_rules "
         "WHERE scope_iso = 'ERCOT' ORDER BY rule_id"),
    ],
    "county_sources": [
        ("counts_by_moratorium",
         "SELECT moratorium_id, COUNT(*) AS n FROM SITEWHY.county_sources "
         "GROUP BY moratorium_id ORDER BY moratorium_id"),
        ("all_sources",
         "SELECT moratorium_id, title FROM SITEWHY.county_sources ORDER BY moratorium_id"),
        ("orphan_sources",
         "SELECT c.moratorium_id, c.title FROM SITEWHY.county_sources c "
         "LEFT JOIN SITEWHY.moratoria m ON c.moratorium_id = m.moratorium_id "
         "WHERE m.moratorium_id IS NULL"),
    ],
}

USL_QUERIES = [
    ("active_with_context",
     "SELECT moratorium_id, state_abbrev, jurisdiction, enacted_status, "
     "state_bill_count, state_bills_enacted, federal_rules, state_rules, "
     "county_source_count FROM SITEWHY.usl_site_screen "
     "WHERE enacted_status IN ('active', 'extended') "
     "ORDER BY state_abbrev, jurisdiction LIMIT 10"),
    ("washington_scope_flip",
     "SELECT moratorium_id, jurisdiction, enacted_status, state_bill_count, "
     "federal_rules, county_source_count FROM SITEWHY.usl_site_screen "
     "WHERE moratorium_id LIKE '%washington%' ORDER BY moratorium_id"),
    ("texas_ercot_rules",
     "SELECT moratorium_id, jurisdiction, state_bill_count, state_rules "
     "FROM SITEWHY.usl_site_screen "
     "WHERE state_abbrev = 'TX' AND state_rules <> '' ORDER BY moratorium_id LIMIT 10"),
]

# Data-quality rule: every USL row must carry a usable join key. A violation
# row means the join leaked; the rule passes when zero rows come back.
DQ_RULE = (
    "null_join_keys",
    "SELECT moratorium_id, state_abbrev FROM SITEWHY.usl_site_screen "
    "WHERE moratorium_id IS NULL OR moratorium_id = '' "
    "OR state_abbrev IS NULL OR state_abbrev = ''",
)


def export_curated_rules(rows_path: Path = RULES_CSV) -> list[dict]:
    """Flatten data/layers/rules.yaml to a CSV Zetaris can register."""
    specs = yaml.safe_load(RULES_YAML.read_text())
    rows = []
    for spec in specs:
        check = spec.get("check") or {}
        if not isinstance(check, dict):
            check = {}
        scope = spec.get("scope") or {}
        rows.append({
            "rule_id": spec.get("id", ""),
            "layer": spec.get("layer", ""),
            "title": spec.get("title", ""),
            "scope_iso": scope.get("iso", "") if isinstance(scope, dict) else "",
            "mw_threshold": check.get("mw_threshold", ""),
            "mw_inclusive": check.get("inclusive", ""),
            "check_label": check.get("label", ""),
            "quote": spec.get("quote", ""),
            "source_url": spec.get("source_url", ""),
            "source_title": spec.get("source_title", ""),
            "as_of": spec.get("as_of", ""),
            "status": spec.get("status", ""),
        })
    write_csv(rows_path, RULES_COLUMNS, rows)
    return rows


def export_county_sources(rows_path: Path = SOURCES_CSV) -> list[dict]:
    """Flatten data/layers/county_sources.yaml to a CSV Zetaris can register."""
    specs = yaml.safe_load(COUNTY_YAML.read_text())
    rows = []
    for moratorium_id, sources in specs.items():
        for source in sources or []:
            rows.append({
                "moratorium_id": moratorium_id,
                "url": source.get("url", ""),
                "title": source.get("title", ""),
            })
    write_csv(rows_path, SOURCES_COLUMNS, rows)
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: ("" if row.get(col) is None else row[col]) for col in columns})


def usl_build_sql(moratoria: str, legislation: str, rules: str, sources: str) -> str:
    """Return the exact SELECT that materializes the USL join table."""
    return f"""SELECT
  m.moratorium_id AS moratorium_id,
  m.state AS state,
  m.state_abbrev AS state_abbrev,
  m.jurisdiction AS jurisdiction,
  m.jurisdiction_type AS jurisdiction_type,
  m.enacted_status AS enacted_status,
  m.current_end_date_iso AS current_end_date_iso,
  COALESCE(b.state_bill_count, 0) AS state_bill_count,
  COALESCE(b.state_bills_enacted, 0) AS state_bills_enacted,
  (SELECT STRING_AGG(rule_id, '|' ORDER BY rule_id)
     FROM read_csv_auto('{rules}', all_varchar=true)
    WHERE layer = 'federal') AS federal_rules,
  COALESCE(r.state_rules, '') AS state_rules,
  COALESCE(s.county_source_count, 0) AS county_source_count,
  COALESCE(s.county_source_titles, '') AS county_source_titles
FROM read_csv_auto('{moratoria}', all_varchar=true) m
LEFT JOIN (
  SELECT state_abbrev,
         COUNT(*) AS state_bill_count,
         SUM(CASE WHEN bill_status_category = 'enacted' THEN 1 ELSE 0 END)
           AS state_bills_enacted
    FROM read_csv_auto('{legislation}', all_varchar=true)
   GROUP BY state_abbrev
) b ON b.state_abbrev = m.state_abbrev
LEFT JOIN (
  SELECT CASE scope_iso WHEN 'ERCOT' THEN 'TX' ELSE scope_iso END AS state_abbrev,
         STRING_AGG(rule_id, '|' ORDER BY rule_id) AS state_rules
    FROM read_csv_auto('{rules}', all_varchar=true)
   WHERE scope_iso <> ''
   GROUP BY 1
) r ON r.state_abbrev = m.state_abbrev
LEFT JOIN (
  SELECT moratorium_id,
         COUNT(*) AS county_source_count,
         STRING_AGG(title, ' || ' ORDER BY title) AS county_source_titles
    FROM read_csv_auto('{sources}', all_varchar=true)
   GROUP BY moratorium_id
) s ON s.moratorium_id = m.moratorium_id
ORDER BY m.state_abbrev, m.jurisdiction, m.moratorium_id"""


def build_usl_csv(out_path: Path = USL_CSV) -> list[dict]:
    """Materialize the USL join locally with DuckDB; returns the rows."""
    con = duckdb.connect()
    try:
        sql = usl_build_sql(
            MORATORIA_CSV.as_posix(), LEGISLATION_CSV.as_posix(),
            RULES_CSV.as_posix(), SOURCES_CSV.as_posix(),
        )
        rows = [dict(zip(USL_COLUMNS, [("" if v is None else str(v)) for v in row], strict=True))
                for row in con.execute(sql).fetchall()]
    finally:
        con.close()
    write_csv(out_path, USL_COLUMNS, rows)
    return rows


class ZetarisError(RuntimeError):
    pass


class ZetarisClient:
    """Minimal run-query client for the local Zetaris SQL-editor proxy."""

    def __init__(self) -> None:
        try:
            self.base_url = os.environ["ZETARIS_BASE_URL"].rstrip("/")
            self.org_id = os.environ["ZETARIS_ORG_ID"]
            self.api_key = os.environ["ZETARIS_API_KEY"]
        except KeyError as exc:
            raise ZetarisError(f"missing environment setting: {exc}") from exc
        if not (self.base_url and self.org_id and self.api_key):
            raise ZetarisError("Zetaris settings are empty; source ~/.hackathon-keys.env first")
        self.client = httpx.Client(timeout=300)

    def run_query(self, sql: str, limit: int = 10000) -> list[dict]:
        try:
            resp = self.client.post(
                f"{self.base_url}/api/proxy/sql-editor/sqls/run-query",
                json={"sql": sql, "limit": limit},
                headers={"Authorization": f"Bearer {self.api_key}", "X-Org-ID": self.org_id},
            )
        except httpx.HTTPError as exc:
            raise ZetarisError(f"Zetaris unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise ZetarisError(f"Zetaris returned {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        cols = body.get("headers") or []
        data = body.get("data") or []
        rows = []
        for row in data:
            rows.append(dict(zip(cols, [("" if v is None else str(v)) for v in row], strict=True)))
        return rows

    def run_ignoring(self, sql: str) -> None:
        try:
            self.run_query(sql, limit=1)
        except ZetarisError:
            pass


def docker_bin() -> str:
    for candidate in DOCKER_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    raise ZetarisError("no docker binary found; start Docker Desktop first")


def stage_file(path: Path) -> str:
    """Copy a CSV into the Zetaris driver container; return its container path."""
    binary, target = docker_bin(), f"{CONTAINER_DIR}/{path.name}"
    subprocess.run([binary, "exec", "zetaris-driver-1", "mkdir", "-p", CONTAINER_DIR], check=True)
    subprocess.run([binary, "cp", str(path), f"zetaris-driver-1:{target}"], check=True)
    return target


def register_csv(client: ZetarisClient, table: str, path: Path) -> int:
    container_path = stage_file(path)
    client.run_ignoring(f'CREATE LIGHTNING DATABASE {SCHEMA} DESCRIBE BY "SiteWhy seed layers"')
    client.run_ignoring(f"DROP LIGHTNING DATABASE TABLE {SCHEMA}.{table}")
    client.run_query(
        f"CREATE LIGHTNING FILESTORE TABLE {table} FROM {SCHEMA} FORMAT CSV OPTIONS ("
        f'path "file://{container_path}", header "true", inferSchema "false", '
        'multiLine "true", escape \'"\')'
    )
    rows = client.run_query(f"SELECT COUNT(*) AS n FROM {SCHEMA}.{table}")
    return int(rows[0]["n"])


def save_json(name: str, payload: dict) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def render_usl_sql() -> str:
    header = (
        "-- SiteWhy Unified Semantic Layer DDL.\n"
        "-- Generated and executed by scripts/zetaris_usl.py against local Zetaris.\n"
        "-- Tables moratoria/state_legislation are pre-existing seed tables, re-registered\n"
        "-- here so setup is automated. curated_rules/county_sources come from\n"
        "-- data/layers/*.yaml via data/seed/*.csv. Plain Spark CREATE VIEW/CTAS does not\n"
        "-- persist across SQL-editor proxy requests on this instance, so the USL is a\n"
        "-- materialized join table built by the SELECT below (DuckDB) and registered as\n"
        "-- a Lightning filestore table.\n\n"
        f'CREATE LIGHTNING DATABASE {SCHEMA} DESCRIBE BY "SiteWhy seed layers";\n'
    )
    tables = {
        "moratoria": MORATORIA_CSV.name,
        "state_legislation": LEGISLATION_CSV.name,
        "curated_rules": RULES_CSV.name,
        "county_sources": SOURCES_CSV.name,
        "usl_site_screen": USL_CSV.name,
    }
    ddl = [header]
    for table, filename in tables.items():
        ddl.append(
            f"DROP LIGHTNING DATABASE TABLE {SCHEMA}.{table};\n"
            f"CREATE LIGHTNING FILESTORE TABLE {table} FROM {SCHEMA} FORMAT CSV OPTIONS (\n"
            f'  path "file://{CONTAINER_DIR}/{filename}", header "true",\n'
            '  inferSchema "false", multiLine "true", escape \'"\');\n'
        )
    ddl.append("-- USL build query (materialized to data/seed/usl_site_screen.csv):\n")
    ddl.append(usl_build_sql(
        MORATORIA_CSV.as_posix(), LEGISLATION_CSV.as_posix(),
        RULES_CSV.as_posix(), SOURCES_CSV.as_posix(),
    ) + ";\n")
    ddl.append("-- Data-quality rule (passes when zero rows come back):\n" + DQ_RULE[1] + ";\n")
    return "\n".join(ddl)


def query_evidence(client: ZetarisClient, name: str, sql: str) -> dict:
    rows = client.run_query(sql)
    print(f"  {name}: {len(rows)} rows")
    return {"name": name, "sql": sql, "row_count": len(rows), "rows": rows[:50]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the SiteWhy USL on local Zetaris")
    parser.add_argument("--offline", action="store_true", help="CSVs + DDL only, no Zetaris")
    args = parser.parse_args()

    print("exporting curated CSVs...")
    rules = export_curated_rules()
    sources = export_county_sources()
    print(f"  curated_rules: {len(rules)} rows -> {RULES_CSV}")
    print(f"  county_sources: {len(sources)} rows -> {SOURCES_CSV}")

    print("materializing the USL join...")
    usl_rows = build_usl_csv()
    print(f"  usl_site_screen: {len(usl_rows)} rows -> {USL_CSV}")

    USL_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    USL_SQL_PATH.write_text(render_usl_sql())
    print(f"  DDL -> {USL_SQL_PATH}")

    if args.offline:
        print("offline mode: skipping Zetaris registration and queries")
        return 0

    try:
        client = ZetarisClient()
        sentry = client.run_query("SELECT 1 AS one")
        assert sentry == [{"one": "1"}]
    except (ZetarisError, AssertionError) as exc:
        print(f"BLOCKED: Zetaris preflight failed: {exc}", file=sys.stderr)
        print("CSVs and DDL were still written; DuckDB fallback keeps serving the app.",
              file=sys.stderr)
        return 2

    print("registering sources in Zetaris...")
    registration = {}
    for table, path in [("moratoria", MORATORIA_CSV), ("state_legislation", LEGISLATION_CSV),
                        ("curated_rules", RULES_CSV), ("county_sources", SOURCES_CSV),
                        ("usl_site_screen", USL_CSV)]:
        count = register_csv(client, table, path)
        print(f"  SITEWHY.{table}: {count} rows")
        registration[table] = {"rows": count}
    save_json("registration.json", {
        "at_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "backend": "zetaris", "tables": registration,
    })

    print("running exploratory queries...")
    for source, queries in EXPLORATORY.items():
        save_json(f"exploratory_{source}.json", {
            "source": source,
            "queries": [query_evidence(client, name, sql) for name, sql in queries],
        })

    print("running USL queries...")
    save_json("usl_queries.json", {
        "queries": [query_evidence(client, name, sql) for name, sql in USL_QUERIES],
    })

    print("running the data-quality rule...")
    dq_name, dq_sql = DQ_RULE
    violations = client.run_query(dq_sql)
    dq = {"name": dq_name, "sql": dq_sql,
          "violation_count": len(violations), "violations": violations[:50],
          "passed": not violations}
    save_json("dq_rule.json", dq)
    print(f"  {dq_name}: {'PASS' if dq['passed'] else 'FAIL'} ({len(violations)} violations)")

    save_json("run.json", {
        "at_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "backend": "zetaris",
        "sources": sorted(registration),
        "exploratory_per_source": {s: len(q) for s, q in EXPLORATORY.items()},
        "usl_queries": len(USL_QUERIES),
        "dq_passed": dq["passed"],
    })
    if not dq["passed"]:
        print("BLOCKED: data-quality rule found violations", file=sys.stderr)
        return 3
    print("USL build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
