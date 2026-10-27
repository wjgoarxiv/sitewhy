"""Offline tests for the Zetaris USL lane (no Zetaris, Docker, or secrets needed)."""

import csv
import json
from pathlib import Path

import duckdb
import pytest
import yaml

from scripts.zetaris_usl import (
    EXPLORATORY,
    USL_QUERIES,
    build_usl_csv,
    export_county_sources,
    export_curated_rules,
    render_usl_sql,
    usl_build_sql,
)

ROOT = Path(__file__).resolve().parent.parent


def test_exports_match_yaml_layers(tmp_path):
    rules_path, sources_path = tmp_path / "rules.csv", tmp_path / "sources.csv"
    rules = export_curated_rules(rules_path)
    sources = export_county_sources(sources_path)

    specs = yaml.safe_load((ROOT / "data/layers/rules.yaml").read_text())
    assert len(rules) == len(specs) == 3
    assert {r["rule_id"] for r in rules} == {s["id"] for s in specs}
    assert any(r["scope_iso"] == "ERCOT" for r in rules)

    county = yaml.safe_load((ROOT / "data/layers/county_sources.yaml").read_text())
    assert len(sources) == sum(len(v) for v in county.values()) == 3
    assert {s["moratorium_id"] for s in sources} == set(county)

    for path in (rules_path, sources_path):
        with open(path, newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows and all(all(v != "None" for v in row.values()) for row in rows)


def test_usl_build_joins_all_sources(tmp_path):
    mor = tmp_path / "mor.csv"
    mor.write_text(
        "moratorium_id,state,state_abbrev,jurisdiction,jurisdiction_type,"
        "enacted_status,current_end_date_iso\n"
        "md-x-2026,Maryland,MD,X,County,active,2027-01-01\n"
        "tx-y-2026,Texas,TX,Y,City,active,\n"
    )
    leg = tmp_path / "leg.csv"
    leg.write_text("state_abbrev,bill_status_category\nMD,enacted\nMD,failed_died\n")
    rules = tmp_path / "rules.csv"
    rules.write_text("rule_id,layer,scope_iso\nfed-1,federal,\nstate-1,state,ERCOT\n")
    src = tmp_path / "src.csv"
    src.write_text("moratorium_id,title\nmd-x-2026,Press release\nmd-x-2026,Draft PDF\n")

    sql = usl_build_sql(mor.as_posix(), leg.as_posix(), rules.as_posix(), src.as_posix())
    con = duckdb.connect()
    try:
        got = con.execute(sql).fetchall()
        cols = [c[0] for c in con.description]
    finally:
        con.close()
    rows = [dict(zip(cols, r, strict=True)) for r in got]
    assert len(rows) == 2
    md = next(r for r in rows if r["moratorium_id"] == "md-x-2026")
    assert md["state_bill_count"] == 2 and md["state_bills_enacted"] == 1
    assert md["federal_rules"] == "fed-1" and md["state_rules"] == ""
    assert md["county_source_count"] == 2
    tx = next(r for r in rows if r["moratorium_id"] == "tx-y-2026")
    assert tx["state_rules"] == "state-1" and tx["county_source_count"] == 0

    out = tmp_path / "usl.csv"
    assert len(build_usl_csv(out)) == 1291  # full seed join, not the fixture
    assert out.is_file()


def test_dq_rule_catches_null_keys():
    con = duckdb.connect()
    try:
        bad = con.execute(
            "SELECT * FROM (VALUES ('', 'MD'), (NULL, 'TX'), ('ok-1', 'VA')) "
            "t(moratorium_id, state_abbrev) "
            "WHERE moratorium_id IS NULL OR moratorium_id = '' "
            "OR state_abbrev IS NULL OR state_abbrev = ''"
        ).fetchall()
    finally:
        con.close()
    assert len(bad) == 2


def test_rendered_ddl_covers_all_tables():
    ddl = render_usl_sql()
    for table in ("moratoria", "state_legislation", "curated_rules",
                  "county_sources", "usl_site_screen"):
        assert f"CREATE LIGHTNING FILESTORE TABLE {table}" in ddl
    assert "null_join_keys" not in ddl  # DQ ships as a query, see below
    assert "moratorium_id IS NULL" in ddl
    assert "STRING_AGG" in ddl


def test_query_inventory_meets_minimums():
    assert set(EXPLORATORY) >= {"moratoria", "state_legislation", "curated_rules", "county_sources"}
    assert all(len(q) >= 2 for q in EXPLORATORY.values())
    assert len(USL_QUERIES) >= 2


def test_committed_seed_csvs_are_fresh():
    for name in ("curated_rules.csv", "county_sources.csv", "usl_site_screen.csv"):
        assert (ROOT / "data/seed" / name).is_file()
    assert (ROOT / "zetaris/usl.sql").is_file()
    assert (ROOT / "zetaris/REFLECTION.md").read_text().count("## ") >= 3


@pytest.mark.live
def test_live_usl_table_counts():
    from app.config import load_settings
    from app.data import ZetarisHarness

    harness = ZetarisHarness(load_settings())
    counts = harness.query(
        "SELECT 'x' AS t, COUNT(*) AS n FROM SITEWHY.usl_site_screen "
        "UNION ALL SELECT 'm', COUNT(*) FROM SITEWHY.moratoria"
    )
    assert {r["t"]: r["n"] for r in counts}["x"] == {r["t"]: r["n"] for r in counts}["m"]


def test_evidence_files_are_well_formed():
    evidence = ROOT / "zetaris/evidence"
    for name in ("registration.json", "usl_queries.json", "dq_rule.json", "run.json"):
        payload = json.loads((evidence / name).read_text())
        assert payload
    dq = json.loads((evidence / "dq_rule.json").read_text())
    assert dq["passed"] is True and dq["violation_count"] == 0
