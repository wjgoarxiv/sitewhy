"""Data layer. Zetaris is the primary backend; DuckDB serves the same SQL when
Zetaris is unreachable. Both expose tables as SITEWHY.<table> and return every
value as a string (or None), so callers see identical rows from either backend.
"""

import shutil
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path

import duckdb
import httpx

from app.config import Settings

SCHEMA = "SITEWHY"
ZETARIS_CONTAINER = "zetaris-driver-1"
ZETARIS_SHARED_DIR = "/home/zetaris/customer-data/shared/sitewhy"


class HarnessError(RuntimeError):
    pass


def _as_str(value) -> str | None:
    return None if value is None else str(value)


class DuckDbHarness:
    backend = "duckdb"

    def __init__(self):
        self.con = duckdb.connect()
        self.con.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    def register_csv(self, table: str, path: Path) -> None:
        self.con.execute(
            f"CREATE OR REPLACE VIEW {SCHEMA}.{table} AS "
            f"SELECT * FROM read_csv_auto('{Path(path).as_posix()}', all_varchar=true)"
        )

    def query(self, sql: str) -> list[dict]:
        try:
            cur = self.con.execute(sql)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, map(_as_str, row), strict=True)) for row in cur.fetchall()]
        except duckdb.Error as exc:
            raise HarnessError(f"duckdb: {exc}") from exc


def docker_stage(path: Path) -> str:
    """Copy a file into the local Zetaris driver container and return its path there."""
    docker = shutil.which("docker") or str(Path.home() / ".docker/bin/docker")
    target = f"{ZETARIS_SHARED_DIR}/{Path(path).name}"
    subprocess.run(
        [docker, "exec", ZETARIS_CONTAINER, "mkdir", "-p", ZETARIS_SHARED_DIR], check=True
    )
    subprocess.run([docker, "cp", str(path), f"{ZETARIS_CONTAINER}:{target}"], check=True)
    return target


class ZetarisHarness:
    backend = "zetaris"

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        stage: Callable[[Path], str] = docker_stage,
    ):
        self.settings = settings
        self.client = client or httpx.Client(timeout=300)
        self.stage = stage

    def _run(self, sql: str, limit: int = 10000) -> dict:
        s = self.settings
        if not s.zetaris_configured:
            raise HarnessError("Zetaris is not configured")
        try:
            resp = self.client.post(
                f"{s.zetaris_base_url.rstrip('/')}/api/proxy/sql-editor/sqls/run-query",
                json={"sql": sql, "limit": limit},
                headers={
                    "Authorization": f"Bearer {s.zetaris_api_key}",
                    "X-Org-ID": s.zetaris_org_id,
                    "X-Request-ID": str(uuid.uuid4()),
                },
            )
        except httpx.HTTPError as exc:
            raise HarnessError(f"Zetaris unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise HarnessError(f"Zetaris returned {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def query(self, sql: str) -> list[dict]:
        body = self._run(sql)
        cols = body.get("headers") or []
        return [dict(zip(cols, map(_as_str, row), strict=True)) for row in body.get("data") or []]

    def _run_ignoring(self, sql: str, expected: str) -> None:
        try:
            self._run(sql)
        except HarnessError as exc:
            if expected not in str(exc):
                raise

    def register_csv(self, table: str, path: Path) -> None:
        container_path = self.stage(Path(path))
        self._run_ignoring(
            f'CREATE LIGHTNING DATABASE {SCHEMA} DESCRIBE BY "SiteWhy seed layers"',
            "already exists",
        )
        self._run_ignoring(f"DROP LIGHTNING DATABASE TABLE {SCHEMA}.{table}", "")
        self._run(
            f"CREATE LIGHTNING FILESTORE TABLE {table} FROM {SCHEMA} FORMAT CSV OPTIONS ("
            f'path "file://{container_path}", header "true", inferSchema "false")'
        )


class FallbackHarness:
    """Query the primary backend; on failure record BLOCKED and use the fallback."""

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.trace: list[dict] = []

    def query(self, sql: str) -> list[dict]:
        try:
            rows = self.primary.query(sql)
        except HarnessError as exc:
            self.trace.append(
                {"backend": self.primary.backend, "status": "BLOCKED", "error": str(exc)[:200]}
            )
        else:
            self.trace.append({"backend": self.primary.backend, "status": "ok", "rows": len(rows)})
            return rows
        rows = self.fallback.query(sql)
        self.trace.append({"backend": self.fallback.backend, "status": "ok", "rows": len(rows)})
        return rows
