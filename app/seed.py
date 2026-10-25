"""Seed layers registered into the data harness (Zetaris or DuckDB)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MORATORIA_CSV = ROOT / "data/seed/moratorium_nation/moratorium_inventory.csv"
STATE_LEGISLATION_CSV = ROOT / "data/seed/moratorium_nation/state_legislation.csv"
MORATORIA_SOURCE = (
    "Moratorium Nation dataset, refreshed 2026-09-23 "
    "(github.com/mjbommar/moratorium-data-2026, CC-BY-4.0)"
)


def register_seed(harness) -> None:
    harness.register_csv("moratoria", MORATORIA_CSV)
    harness.register_csv("state_legislation", STATE_LEGISLATION_CSV)
