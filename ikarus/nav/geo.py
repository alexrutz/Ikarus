"""Great-circle geodesy and magnetic variation.

All angles in degrees, distances in nautical miles unless suffixed.
Spherical earth is plenty for FMS guidance (errors < 0.5%).
"""

from __future__ import annotations

import math

EARTH_RADIUS_NM = 3440.065
DEG = math.pi / 180.0


def dist_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    dlat = (lat2 - lat1) * DEG
    dlon = (lon2 - lon1) * DEG
    a = math.sin(dlat / 2) ** 2 \
        + math.cos(lat1 * DEG) * math.cos(lat2 * DEG) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial true course from point 1 to point 2 (0..360)."""
    dlon = (lon2 - lon1) * DEG
    y = math.sin(dlon) * math.cos(lat2 * DEG)
    x = math.cos(lat1 * DEG) * math.sin(lat2 * DEG) \
        - math.sin(lat1 * DEG) * math.cos(lat2 * DEG) * math.cos(dlon)
    return (math.atan2(y, x) / DEG) % 360.0


def destination(lat: float, lon: float, course_deg: float, d_nm: float
                ) -> tuple[float, float]:
    """Point d_nm along course from (lat, lon)."""
    delta = d_nm / EARTH_RADIUS_NM
    theta = course_deg * DEG
    phi1, lam1 = lat * DEG, lon * DEG
    phi2 = math.asin(math.sin(phi1) * math.cos(delta)
                     + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lam2 = lam1 + math.atan2(math.sin(theta) * math.sin(delta) * math.cos(phi1),
                             math.cos(delta) - math.sin(phi1) * math.sin(phi2))
    return phi2 / DEG, ((lam2 / DEG + 540) % 360) - 180


def cross_track_nm(lat: float, lon: float,
                   lat1: float, lon1: float,
                   lat2: float, lon2: float) -> float:
    """Signed cross-track distance from the great circle leg 1->2.

    Positive = right of course.
    """
    d13 = dist_nm(lat1, lon1, lat, lon) / EARTH_RADIUS_NM
    brg13 = bearing_deg(lat1, lon1, lat, lon) * DEG
    brg12 = bearing_deg(lat1, lon1, lat2, lon2) * DEG
    return math.asin(math.sin(d13) * math.sin(brg13 - brg12)) * EARTH_RADIUS_NM


def along_track_nm(lat: float, lon: float,
                   lat1: float, lon1: float,
                   lat2: float, lon2: float) -> float:
    """Distance along leg 1->2 of the point's abeam projection."""
    d13 = dist_nm(lat1, lon1, lat, lon) / EARTH_RADIUS_NM
    xtk = cross_track_nm(lat, lon, lat1, lon1, lat2, lon2) / EARTH_RADIUS_NM
    cos_d13, cos_xtk = math.cos(d13), math.cos(xtk)
    if abs(cos_xtk) < 1e-12:
        return 0.0
    return math.acos(max(-1.0, min(1.0, cos_d13 / cos_xtk))) * EARTH_RADIUS_NM


def angle_diff_deg(target: float, current: float) -> float:
    """Shortest signed angular difference target-current in (-180, 180]."""
    d = (target - current) % 360.0
    return d - 360.0 if d > 180.0 else d


def magvar_deg(lat: float, lon: float) -> float:
    """Coarse magnetic variation (east positive), bilinear over a grid.

    Good to a couple of degrees over EU/US — sufficient for display and
    course intercepts; replaceable by WMM later without touching callers.
    """
    # 30-degree grid, 2025-ish epoch, rows lat -60..75, cols lon -180..180
    grid = {
        # lat: {lon: var}
        60: {-150: 16, -120: 17, -90: -8, -60: -17, -30: -8, 0: 2, 30: 12, 60: 14, 90: 6, 120: -5, 150: -11, 180: 5},
        45: {-150: 16, -120: 15, -90: -3, -60: -16, -30: -7, 0: 1, 30: 7, 60: 9, 90: 3, 120: -7, 150: -10, 180: 2},
        30: {-150: 12, -120: 12, -90: 2, -60: -13, -30: -6, 0: 0, 30: 4, 60: 4, 90: 0, 120: -4, 150: -6, 180: 0},
        0:  {-150: 9, -120: 9, -90: 0, -60: -12, -30: -12, 0: -2, 30: 2, 60: 2, 90: -2, 120: 0, 150: 4, 180: 6},
        -30: {-150: 12, -120: 8, -90: 2, -60: -5, -30: -18, 0: -12, 30: -10, 60: -18, 90: -30, 120: 2, 150: 10, 180: 13},
    }
    lats = sorted(grid)
    lat = max(lats[0], min(lats[-1], lat))
    lat0 = max(l for l in lats if l <= lat)
    lat1 = min(l for l in lats if l >= lat)
    lon = ((lon + 180) % 360) - 180

    def row_val(row: dict, lo: float) -> float:
        lons = sorted(row)
        lo = max(lons[0], min(lons[-1], lo))
        l0 = max(x for x in lons if x <= lo)
        l1 = min(x for x in lons if x >= lo)
        if l0 == l1:
            return row[l0]
        f = (lo - l0) / (l1 - l0)
        return row[l0] * (1 - f) + row[l1] * f

    v0 = row_val(grid[lat0], lon)
    v1 = row_val(grid[lat1], lon)
    if lat0 == lat1:
        return v0
    f = (lat - lat0) / (lat1 - lat0)
    return v0 * (1 - f) + v1 * f
