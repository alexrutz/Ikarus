"""Flight plan model: waypoint assembly, sequencing, DIR TO.

The plan is assembled from: departure runway + SID legs, enroute fixes
(navaid/airport idents or procedure fixes), STAR legs, approach legs and
the destination runway threshold. Legs are simple great-circle tracks
(TF); turn anticipation handles the corners.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ikarus.nav import geo, procedures
from ikarus.nav.database import NavDatabase, Runway


@dataclass(frozen=True)
class Waypoint:
    ident: str
    lat: float
    lon: float
    alt_above: float | None = None
    alt_below: float | None = None
    speed: float | None = None
    kind: str = "fix"            # fix | runway | airport


class PlanError(Exception):
    pass


class FlightPlan:
    def __init__(self, navdb: NavDatabase):
        self.navdb = navdb
        self.origin: str = ""
        self.dest: str = ""
        self.dep_runway: Runway | None = None
        self.arr_runway: Runway | None = None
        self.sid_name = ""
        self.star_name = ""
        self.appr_name = ""
        self._dep_procs: procedures.AirportProcedures | None = None
        self._arr_procs: procedures.AirportProcedures | None = None
        self._enroute: list[Waypoint] = []
        self.waypoints: list[Waypoint] = []
        self.active_idx: int = -1
        # DIR TO anchor: guidance flies from this point to the active wpt
        self.dirto_anchor: tuple[float, float] | None = None
        self.version = 0

    # --- construction ---------------------------------------------------------

    def set_route(self, origin: str, dest: str) -> None:
        for icao in (origin, dest):
            if self.navdb.airport(icao) is None:
                raise PlanError(f"unknown airport {icao}")
        self.origin, self.dest = origin.upper(), dest.upper()
        self.dep_runway = self.arr_runway = None
        self.sid_name = self.star_name = self.appr_name = ""
        self._dep_procs = procedures.load_airport(self.origin)
        self._arr_procs = procedures.load_airport(self.dest)
        self._enroute = []
        self._rebuild()

    def set_dep_runway(self, rwy: str) -> None:
        runway = self.navdb.runway(self.origin, rwy)
        if runway is None:
            raise PlanError(f"no runway {rwy} at {self.origin}")
        self.dep_runway = runway
        if self.sid_name and self._dep_procs and \
                self.sid_name in self._dep_procs.sids:
            sid = self._dep_procs.sids[self.sid_name]
            if sid.runways and runway.ident not in sid.runways:
                self.sid_name = ""
        self._rebuild()

    def set_sid(self, name: str) -> None:
        if not self._dep_procs or name not in self._dep_procs.sids:
            raise PlanError(f"no SID {name} at {self.origin}")
        self.sid_name = name
        self._rebuild()

    def set_star(self, name: str) -> None:
        if not self._arr_procs or name not in self._arr_procs.stars:
            raise PlanError(f"no STAR {name} at {self.dest}")
        self.star_name = name
        self._rebuild()

    def set_approach(self, name: str) -> None:
        if not self._arr_procs or name not in self._arr_procs.approaches:
            raise PlanError(f"no approach {name} at {self.dest}")
        appr = self._arr_procs.approaches[name]
        runway = self.navdb.runway(self.dest, appr.runway)
        if runway is None:
            raise PlanError(f"approach runway {appr.runway} not in navdata")
        self.appr_name = name
        self.arr_runway = runway
        self._rebuild()

    def insert_fix(self, ident: str, at_idx: int | None = None) -> None:
        """Insert an enroute fix (navaid ident, airport, or procedure fix)."""
        wpt = self._resolve_fix(ident)
        if wpt is None:
            raise PlanError(f"unknown fix {ident}")
        if at_idx is None:
            self._enroute.append(wpt)
        else:
            # position within the enroute segment, clamped
            seg_idx = max(0, min(len(self._enroute), at_idx))
            self._enroute.insert(seg_idx, wpt)
        self._rebuild(keep_active=True)

    def delete_enroute_fix(self, ident: str) -> None:
        before = len(self._enroute)
        self._enroute = [w for w in self._enroute if w.ident != ident.upper()]
        if len(self._enroute) == before:
            raise PlanError(f"{ident} not an enroute fix")
        self._rebuild(keep_active=True)

    def _resolve_fix(self, ident: str) -> Waypoint | None:
        ident = ident.upper()
        for procs in (self._dep_procs, self._arr_procs):
            if procs and ident in procs.fixes:
                lat, lon = procs.fixes[ident]
                return Waypoint(ident, lat, lon)
        near = None
        if self.navdb.airport(self.origin):
            apt = self.navdb.airport(self.origin)
            near = (apt.lat, apt.lon)
        navaid = self.navdb.navaid(ident, near=near)
        if navaid:
            return Waypoint(navaid.ident, navaid.lat, navaid.lon)
        apt = self.navdb.airport(ident)
        if apt:
            return Waypoint(apt.ident, apt.lat, apt.lon, kind="airport")
        return None

    def _rebuild(self, keep_active: bool = False) -> None:
        active_ident = None
        if keep_active and 0 <= self.active_idx < len(self.waypoints):
            active_ident = self.waypoints[self.active_idx].ident

        wpts: list[Waypoint] = []

        def add(wpt: Waypoint) -> None:
            if wpts and wpts[-1].ident == wpt.ident:
                return  # merge duplicate joins (SID exit == enroute entry)
            wpts.append(wpt)

        if self.dep_runway:
            r = self.dep_runway
            add(Waypoint(f"{self.origin}{r.ident}", r.lat, r.lon, kind="runway"))
        elif self.origin:
            apt = self.navdb.airport(self.origin)
            add(Waypoint(self.origin, apt.lat, apt.lon, kind="airport"))
        if self.sid_name and self._dep_procs:
            for leg in self._dep_procs.sids[self.sid_name].legs:
                add(Waypoint(leg.fix, leg.lat, leg.lon,
                             leg.alt_above, leg.alt_below, leg.speed))
        for wpt in self._enroute:
            add(wpt)
        if self.star_name and self._arr_procs:
            for leg in self._arr_procs.stars[self.star_name].legs:
                add(Waypoint(leg.fix, leg.lat, leg.lon,
                             leg.alt_above, leg.alt_below, leg.speed))
        if self.appr_name and self._arr_procs:
            for leg in self._arr_procs.approaches[self.appr_name].legs:
                add(Waypoint(leg.fix, leg.lat, leg.lon,
                             leg.alt_above, leg.alt_below, leg.speed))
        if self.arr_runway:
            r = self.arr_runway
            add(Waypoint(f"{self.dest}{r.ident}", r.lat, r.lon,
                         alt_above=None, alt_below=None, kind="runway"))
        elif self.dest:
            apt = self.navdb.airport(self.dest)
            add(Waypoint(self.dest, apt.lat, apt.lon, kind="airport"))

        self.waypoints = wpts
        self.version += 1
        if active_ident:
            for i, w in enumerate(wpts):
                if w.ident == active_ident:
                    self.active_idx = i
                    break
            else:
                self.active_idx = min(1, len(wpts) - 1)
        else:
            self.active_idx = min(1, len(wpts) - 1)
            self.dirto_anchor = None

    # --- runtime ---------------------------------------------------------------

    @property
    def active(self) -> Waypoint | None:
        if 0 <= self.active_idx < len(self.waypoints):
            return self.waypoints[self.active_idx]
        return None

    def leg_from(self) -> tuple[float, float] | None:
        """Start point of the active leg (previous wpt or DIR TO anchor)."""
        if self.dirto_anchor:
            return self.dirto_anchor
        if self.active_idx >= 1:
            prev = self.waypoints[self.active_idx - 1]
            return (prev.lat, prev.lon)
        return None

    def direct_to(self, ident: str, from_lat: float, from_lon: float) -> None:
        ident = ident.upper()
        for i, w in enumerate(self.waypoints):
            if w.ident == ident:
                self.active_idx = i
                self.dirto_anchor = (from_lat, from_lon)
                self.version += 1
                return
        # not in the plan: resolve and insert as next fix
        wpt = self._resolve_fix(ident)
        if wpt is None:
            raise PlanError(f"unknown fix {ident}")
        self.waypoints.insert(max(self.active_idx, 0) + 1 if self.waypoints else 0, wpt)
        self.active_idx = self.waypoints.index(wpt)
        self.dirto_anchor = (from_lat, from_lon)
        self.version += 1

    def sequence(self, lat: float, lon: float, gs_kts: float,
                 roll_limit_deg: float = 25.0) -> bool:
        """Advance the active waypoint at the turn-anticipation point."""
        active = self.active
        if active is None or self.active_idx >= len(self.waypoints) - 1:
            return False
        dist = geo.dist_nm(lat, lon, active.lat, active.lon)
        nxt = self.waypoints[self.active_idx + 1]
        crs_in = geo.bearing_deg(lat, lon, active.lat, active.lon)
        crs_out = geo.bearing_deg(active.lat, active.lon, nxt.lat, nxt.lon)
        turn = abs(geo.angle_diff_deg(crs_out, crs_in))
        # turn radius at ground speed and the bank limit
        gs_fps = max(gs_kts, 60.0) * 1.68781
        radius_nm = gs_fps ** 2 / (32.17 * math.tan(
            math.radians(roll_limit_deg))) / 6076.12
        anticipation = radius_nm * math.tan(
            math.radians(min(turn, 120.0) / 2)) + 0.1
        if dist <= anticipation:
            self.active_idx += 1
            self.dirto_anchor = None
            self.version += 1
            return True
        return False
