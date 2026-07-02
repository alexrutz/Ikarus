"""Terminal procedures: SID/STAR/approach loader.

Procedures are hand-authored JSON under data/navdata/procedures/{ICAO}.json
using a small subset of ARINC-424 leg semantics (IF/TF/CF) so a future
FAA CIFP importer can emit the same schema. Fixes carry their own
coordinates, so procedures work without an enroute fix database.

Schema per airport file:
{
  "fixes":   {"IDENT": [lat, lon], ...},
  "sids":    {"NAME": {"runways": ["25C", ...], "legs": [LEG, ...]}},
  "stars":   {"NAME": {"runways": [...], "legs": [...]}},
  "approaches": {
     "ILS25L": {"runway": "25L", "loc_freq_khz": 111100, "course_mag": 249,
                "gs_deg": 3.0, "legs": [...]}
  }
}
LEG: {"fix": "IDENT", "type": "TF", "alt_above": 4000, "alt_below": null,
      "speed": 250}   (constraints optional)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ikarus import config


@dataclass(frozen=True)
class ProcLeg:
    fix: str
    lat: float
    lon: float
    leg_type: str = "TF"
    alt_above: float | None = None   # at-or-above constraint
    alt_below: float | None = None   # at-or-below constraint
    speed: float | None = None       # at-or-below speed constraint


@dataclass(frozen=True)
class Procedure:
    name: str
    kind: str                        # sid | star | approach
    legs: tuple[ProcLeg, ...]
    runways: tuple[str, ...] = ()
    # approach only:
    runway: str = ""
    loc_freq_khz: float = 0.0
    course_mag: float = 0.0
    gs_deg: float = 3.0


@dataclass
class AirportProcedures:
    icao: str
    fixes: dict[str, tuple[float, float]] = field(default_factory=dict)
    sids: dict[str, Procedure] = field(default_factory=dict)
    stars: dict[str, Procedure] = field(default_factory=dict)
    approaches: dict[str, Procedure] = field(default_factory=dict)


def _parse_legs(raw_legs: list[dict], fixes: dict[str, tuple[float, float]],
                icao: str) -> tuple[ProcLeg, ...]:
    legs = []
    for leg in raw_legs:
        fix = leg["fix"]
        if fix not in fixes:
            raise ValueError(f"{icao}: leg fix {fix!r} missing from fixes")
        lat, lon = fixes[fix]
        legs.append(ProcLeg(
            fix=fix, lat=lat, lon=lon,
            leg_type=leg.get("type", "TF"),
            alt_above=leg.get("alt_above"),
            alt_below=leg.get("alt_below"),
            speed=leg.get("speed"),
        ))
    return tuple(legs)


def load_airport(icao: str, base_dir: Path | None = None
                 ) -> AirportProcedures | None:
    path = (base_dir or config.PROCEDURES_DIR) / f"{icao.upper()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf8"))
    fixes = {k: (v[0], v[1]) for k, v in data.get("fixes", {}).items()}
    result = AirportProcedures(icao=icao.upper(), fixes=fixes)
    for name, sid in data.get("sids", {}).items():
        result.sids[name] = Procedure(
            name=name, kind="sid",
            legs=_parse_legs(sid["legs"], fixes, icao),
            runways=tuple(sid.get("runways", ())))
    for name, star in data.get("stars", {}).items():
        result.stars[name] = Procedure(
            name=name, kind="star",
            legs=_parse_legs(star["legs"], fixes, icao),
            runways=tuple(star.get("runways", ())))
    for name, app in data.get("approaches", {}).items():
        result.approaches[name] = Procedure(
            name=name, kind="approach",
            legs=_parse_legs(app.get("legs", []), fixes, icao),
            runway=app["runway"],
            loc_freq_khz=app.get("loc_freq_khz", 0.0),
            course_mag=app.get("course_mag", 0.0),
            gs_deg=app.get("gs_deg", 3.0))
    return result
