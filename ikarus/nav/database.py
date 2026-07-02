"""NavDatabase: read-side queries against the navdata SQLite store.

Builds the database from the committed seed CSVs on first use if the
(gitignored) navdata.db is missing.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ikarus import config
from ikarus.nav import ingest

SEED_DIR = config.DATA_DIR / "navdata" / "seed"


@dataclass(frozen=True)
class Airport:
    ident: str
    name: str
    lat: float
    lon: float
    elev_ft: float


@dataclass(frozen=True)
class Runway:
    airport_ident: str
    ident: str
    lat: float
    lon: float
    elev_ft: float
    heading_true: float
    length_ft: float
    opposite_ident: str


@dataclass(frozen=True)
class Navaid:
    ident: str
    name: str
    type: str
    freq_khz: float
    lat: float
    lon: float
    elev_ft: float


class NavDatabase:
    def __init__(self, db_path: Path | None = None):
        path = db_path or config.NAVDATA_DB
        if not path.exists():
            ingest.build_db(SEED_DIR, path)
        self._con = sqlite3.connect(path)
        self._con.row_factory = sqlite3.Row

    def airport(self, ident: str) -> Airport | None:
        row = self._con.execute(
            "SELECT * FROM airports WHERE ident = ?", (ident.upper(),)
        ).fetchone()
        if row is None:
            return None
        return Airport(row["ident"], row["name"], row["lat"], row["lon"],
                       row["elev_ft"] or 0.0)

    def runways(self, airport_ident: str) -> list[Runway]:
        rows = self._con.execute(
            "SELECT * FROM runways WHERE airport_ident = ?",
            (airport_ident.upper(),)).fetchall()
        return [Runway(r["airport_ident"], r["ident"], r["lat"], r["lon"],
                       r["elev_ft"] or 0.0, r["heading_true"] or 0.0,
                       r["length_ft"] or 0.0, r["opposite_ident"] or "")
                for r in rows]

    def runway(self, airport_ident: str, rwy_ident: str) -> Runway | None:
        for r in self.runways(airport_ident):
            if r.ident == rwy_ident.upper():
                return r
        return None

    def navaid(self, ident: str, near: tuple[float, float] | None = None
               ) -> Navaid | None:
        """Navaid by ident; if several share it, the one nearest `near`."""
        rows = self._con.execute(
            "SELECT * FROM navaids WHERE ident = ?", (ident.upper(),)
        ).fetchall()
        if not rows:
            return None
        if near and len(rows) > 1:
            rows.sort(key=lambda r: (r["lat"] - near[0]) ** 2
                      + (r["lon"] - near[1]) ** 2)
        r = rows[0]
        return Navaid(r["ident"], r["name"], r["type"], r["freq_khz"] or 0.0,
                      r["lat"], r["lon"], r["elev_ft"] or 0.0)

    def navaids_near(self, lat: float, lon: float, radius_nm: float = 100
                     ) -> list[Navaid]:
        dlat = radius_nm / 60.0
        dlon = radius_nm / 60.0 / max(0.2, math.cos(math.radians(lat)))
        rows = self._con.execute(
            "SELECT * FROM navaids WHERE lat BETWEEN ? AND ? "
            "AND lon BETWEEN ? AND ?",
            (lat - dlat, lat + dlat, lon - dlon, lon + dlon)).fetchall()
        return [Navaid(r["ident"], r["name"], r["type"], r["freq_khz"] or 0.0,
                       r["lat"], r["lon"], r["elev_ft"] or 0.0) for r in rows]

    def navaid_by_freq(self, freq_khz: float, lat: float, lon: float
                       ) -> Navaid | None:
        """Nearest navaid on the given frequency (VOR tuning)."""
        rows = self._con.execute(
            "SELECT * FROM navaids WHERE abs(freq_khz - ?) < 5", (freq_khz,)
        ).fetchall()
        if not rows:
            return None
        rows.sort(key=lambda r: (r["lat"] - lat) ** 2 + (r["lon"] - lon) ** 2)
        r = rows[0]
        return Navaid(r["ident"], r["name"], r["type"], r["freq_khz"] or 0.0,
                      r["lat"], r["lon"], r["elev_ft"] or 0.0)

    def close(self) -> None:
        self._con.close()
