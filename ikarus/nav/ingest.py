"""OurAirports CSV -> SQLite ingest.

The repo ships a seed extract (large airports worldwide, their runways,
navaids for Europe + US west coast) under data/navdata/seed/, so the
simulator works offline out of the box. `scripts/fetch_navdata.py`
downloads the full dataset over the network into the same schema.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE airports (
    ident TEXT PRIMARY KEY,      -- ICAO
    name TEXT, type TEXT,
    lat REAL, lon REAL, elev_ft REAL,
    iso_country TEXT
);
CREATE TABLE runways (
    airport_ident TEXT,
    ident TEXT,                  -- e.g. 25L (le/he split into two rows)
    lat REAL, lon REAL, elev_ft REAL,
    heading_true REAL,
    length_ft REAL, width_ft REAL,
    opposite_ident TEXT
);
CREATE INDEX idx_runways_airport ON runways(airport_ident);
CREATE TABLE navaids (
    ident TEXT, name TEXT, type TEXT,
    freq_khz REAL,
    lat REAL, lon REAL, elev_ft REAL,
    magvar REAL
);
CREATE INDEX idx_navaids_ident ON navaids(ident);
CREATE INDEX idx_navaids_latlon ON navaids(cast(lat AS INTEGER), cast(lon AS INTEGER));
"""


def _f(row: dict, key: str) -> float | None:
    v = row.get(key, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_db(csv_dir: Path, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    with open(csv_dir / "airports.csv", newline="", encoding="utf8") as f:
        rows = [
            (r["ident"], r["name"], r["type"],
             _f(r, "latitude_deg"), _f(r, "longitude_deg"),
             _f(r, "elevation_ft"), r["iso_country"])
            for r in csv.DictReader(f)
            if r["type"] in ("large_airport", "medium_airport")
        ]
    con.executemany("INSERT OR REPLACE INTO airports VALUES (?,?,?,?,?,?,?)", rows)

    with open(csv_dir / "runways.csv", newline="", encoding="utf8") as f:
        rows = []
        for r in csv.DictReader(f):
            if r.get("closed") == "1":
                continue
            for end, opp in (("le", "he"), ("he", "le")):
                lat, lon = _f(r, f"{end}_latitude_deg"), _f(r, f"{end}_longitude_deg")
                if lat is None or lon is None or not r[f"{end}_ident"]:
                    continue
                rows.append((
                    r["airport_ident"], r[f"{end}_ident"], lat, lon,
                    _f(r, f"{end}_elevation_ft"),
                    _f(r, f"{end}_heading_degT"),
                    _f(r, "length_ft"), _f(r, "width_ft"),
                    r[f"{opp}_ident"],
                ))
    con.executemany("INSERT INTO runways VALUES (?,?,?,?,?,?,?,?,?)", rows)

    with open(csv_dir / "navaids.csv", newline="", encoding="utf8") as f:
        rows = [
            (r["ident"], r["name"], r["type"], _f(r, "frequency_khz"),
             _f(r, "latitude_deg"), _f(r, "longitude_deg"),
             _f(r, "elevation_ft"), _f(r, "magnetic_variation_deg"))
            for r in csv.DictReader(f)
            if _f(r, "latitude_deg") is not None
        ]
    con.executemany("INSERT INTO navaids VALUES (?,?,?,?,?,?,?,?)", rows)

    con.commit()
    con.close()
