"""VNAV vertical profile: top-of-descent, profile deviation, phase.

Deliberately simplified (per design): a geometric ~3 deg idle-descent
path back-computed from the destination field elevation + 3000 ft at
10 nm; climbs respect at-or-below constraints by level-off. Enough for
correct FMA/managed-mode behavior and the ND ToD arrow.
"""

from __future__ import annotations

from ikarus.fms.flightplan import FlightPlan
from ikarus.nav import geo

DESCENT_GRADIENT_FT_PER_NM = 318.0   # ~3 degrees
FINAL_FIX_AGL_FT = 3000.0
FINAL_FIX_DIST_NM = 10.0


def dist_to_dest_nm(plan: FlightPlan, lat: float, lon: float) -> float:
    """Along-route distance to the destination."""
    active = plan.active
    if active is None:
        return 0.0
    d = geo.dist_nm(lat, lon, active.lat, active.lon)
    for i in range(plan.active_idx, len(plan.waypoints) - 1):
        a, b = plan.waypoints[i], plan.waypoints[i + 1]
        d += geo.dist_nm(a.lat, a.lon, b.lat, b.lon)
    return d


def profile_alt_ft(dist_to_dest: float, dest_elev_ft: float,
                   cruise_alt_ft: float) -> float:
    """Descent-profile altitude at the given distance to destination."""
    if dist_to_dest <= FINAL_FIX_DIST_NM:
        base = dest_elev_ft + FINAL_FIX_AGL_FT
        return base * (dist_to_dest / FINAL_FIX_DIST_NM) \
            + dest_elev_ft * (1 - dist_to_dest / FINAL_FIX_DIST_NM) \
            + 0.0
    alt = dest_elev_ft + FINAL_FIX_AGL_FT \
        + (dist_to_dest - FINAL_FIX_DIST_NM) * DESCENT_GRADIENT_FT_PER_NM
    return min(alt, cruise_alt_ft)


def tod_dist_nm(dist_to_dest: float, alt_ft: float,
                dest_elev_ft: float) -> float:
    """Along-track distance from here to the top of descent (<0 = past)."""
    descend_ft = alt_ft - (dest_elev_ft + FINAL_FIX_AGL_FT)
    if descend_ft <= 0:
        return -1.0
    descent_track_nm = descend_ft / DESCENT_GRADIENT_FT_PER_NM \
        + FINAL_FIX_DIST_NM
    return dist_to_dest - descent_track_nm


def next_alt_below_constraint(plan: FlightPlan) -> float | None:
    """Lowest upcoming at-or-below constraint ahead of the aircraft."""
    lowest = None
    for i in range(max(plan.active_idx, 0), len(plan.waypoints)):
        c = plan.waypoints[i].alt_below
        if c is not None and (lowest is None or c < lowest):
            lowest = c
    return lowest
