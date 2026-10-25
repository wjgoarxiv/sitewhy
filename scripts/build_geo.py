"""Build data/geo/eia861_county_utilities.csv from EIA-861 (2025) for the
covered states. Usage: uv run --with openpyxl python scripts/build_geo.py <unzipped f8612025 dir>
Source: https://www.eia.gov/electricity/data/eia861/ (public domain, U.S. EIA).
"""

import csv
import sys
from pathlib import Path

import openpyxl

STATES = {"MD", "TX", "AZ"}
RTOS = ["CAISO", "ERCOT", "PJM", "NYISO", "SPP", "MISO", "ISONE"]
OUT = Path(__file__).resolve().parent.parent / "data/geo/eia861_county_utilities.csv"


def rows(path: Path, sheet: str):
    return openpyxl.load_workbook(path, read_only=True)[sheet].iter_rows(values_only=True)


def main(src: Path) -> None:
    it = rows(src / "Utility_Data_2025.xlsx", "States")
    next(it)
    header = list(next(it))
    rto_cols = {name: header.index(name, header.index("CAISO")) for name in RTOS}
    utilities = {}
    for r in it:
        rtos = [name for name, i in rto_cols.items() if r[i] == "Y"]
        record = {"ownership": r[4], "nerc_region": r[5], "rtos": ";".join(rtos)}
        # A utility files one row per state; prefer the covered-state row when present.
        if r[1] not in utilities or r[3] in STATES:
            utilities[r[1]] = record

    it = rows(src / "Service_Territory_2025.xlsx", "Counties_States")
    next(it)
    out = []
    for _, num, name, _, state, county in it:
        if state not in STATES:
            continue
        u = utilities.get(num, {})
        out.append(
            {
                "state": state,
                "county": county,
                "utility_number": num,
                "utility_name": name,
                "ownership": u.get("ownership", ""),
                "nerc_region": u.get("nerc_region", ""),
                "rtos": u.get("rtos", ""),
            }
        )
    out.sort(key=lambda d: (d["state"], d["county"], d["utility_name"]))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} rows to {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
