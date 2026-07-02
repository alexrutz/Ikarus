"""LNAV lateral guidance: cross-track + track-angle-error -> roll command."""

from __future__ import annotations

from ikarus.fms.flightplan import FlightPlan
from ikarus.nav import geo

XTK_KP = 8.0            # deg of intercept angle per nm of cross-track
XTK_INTERCEPT_MAX = 45.0
TAE_KP = 1.4            # deg of bank per deg of track error
BANK_LIMIT_DEG = 25.0


def compute(plan: FlightPlan, lat: float, lon: float, track_true: float,
            gs_kts: float) -> tuple[float, float, float, float] | None:
    """Return (roll_cmd_deg, xtk_nm, course_true, dtg_nm) or None."""
    active = plan.active
    start = plan.leg_from()
    if active is None:
        return None
    if start is None:
        # first waypoint with no prior leg: home straight onto it
        course = geo.bearing_deg(lat, lon, active.lat, active.lon)
        xtk = 0.0
    else:
        course = geo.bearing_deg(lat, lon, active.lat, active.lon) \
            if geo.dist_nm(*start, active.lat, active.lon) < 0.5 else \
            geo.bearing_deg(start[0], start[1], active.lat, active.lon)
        xtk = geo.cross_track_nm(lat, lon, start[0], start[1],
                                 active.lat, active.lon)
    dtg = geo.dist_nm(lat, lon, active.lat, active.lon)

    # desired track: leg course corrected toward the leg by the intercept
    intercept = max(-XTK_INTERCEPT_MAX, min(XTK_INTERCEPT_MAX, -XTK_KP * xtk))
    desired_track = (course + intercept) % 360.0
    tae = geo.angle_diff_deg(desired_track, track_true)
    roll = max(-BANK_LIMIT_DEG, min(BANK_LIMIT_DEG, TAE_KP * tae))
    return roll, xtk, course, dtg
