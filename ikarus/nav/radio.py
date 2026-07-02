"""RadioSystem: VOR/DME receivers and the ILS.

NAV1/NAV2 tune by frequency (commands `radio.nav1.set` etc.); the ILS is
auto-tuned from the approach selected in the FMS (as the real aircraft
auto-tunes from the F-PLN). LOC/GS deviations are computed geometrically
from the runway threshold, approach course and glideslope angle.
"""

from __future__ import annotations

import math

from ikarus.nav import geo
from ikarus.nav.database import NavDatabase
from ikarus.systems.base import System

VOR_RANGE_NM = 130.0
LOC_RANGE_NM = 25.0
LOC_DOT_DEG = 1.25       # 1 dot of localizer deviation
GS_DOT_DEG = 0.35        # 1 dot of glideslope deviation
GS_ANTENNA_NM = 0.16     # glideslope antenna ~300 m past the threshold
TCH_FT = 50.0


class RadioSystem(System):
    name = "radio"

    def __init__(self, navdb: NavDatabase):
        super().__init__()
        self.navdb = navdb
        self._nav = [None, None]  # cached tuned stations
        self._tuned = [0.0, 0.0]

    def update(self, dt: float) -> None:
        radio, fdm, fms = self.state.radio, self.state.fdm, self.state.fms
        magvar = geo.magvar_deg(fdm.lat_deg, fdm.lon_deg)

        for i, freq in enumerate((radio.nav1_freq_khz, radio.nav2_freq_khz)):
            if freq != self._tuned[i]:
                self._tuned[i] = freq
                self._nav[i] = self.navdb.navaid_by_freq(
                    freq, fdm.lat_deg, fdm.lon_deg) if freq else None
            station = self._nav[i]
            ok, ident, brg, dme = False, "", 0.0, 0.0
            if station:
                dme = geo.dist_nm(fdm.lat_deg, fdm.lon_deg,
                                  station.lat, station.lon)
                if dme < VOR_RANGE_NM:
                    ok = True
                    ident = station.ident
                    brg = (geo.bearing_deg(fdm.lat_deg, fdm.lon_deg,
                                           station.lat, station.lon)
                           - magvar) % 360.0
            if i == 0:
                radio.nav1_ok, radio.nav1_ident = ok, ident
                radio.nav1_bearing_mag, radio.nav1_dme_nm = brg, round(dme, 1)
            else:
                radio.nav2_ok, radio.nav2_ident = ok, ident
                radio.nav2_bearing_mag, radio.nav2_dme_nm = brg, round(dme, 1)

        # --- ILS from the FMS-selected approach -----------------------------
        radio.ils_ok = False
        if fms.appr_freq_khz and fms.appr_thr_lat:
            thr_lat, thr_lon = fms.appr_thr_lat, fms.appr_thr_lon
            course_true = (fms.appr_course_mag
                           + geo.magvar_deg(thr_lat, thr_lon)) % 360.0
            dist_thr = geo.dist_nm(fdm.lat_deg, fdm.lon_deg, thr_lat, thr_lon)
            # front-course coverage: aircraft must be on the approach side
            brg_from_thr = geo.bearing_deg(thr_lat, thr_lon,
                                           fdm.lat_deg, fdm.lon_deg)
            off_axis = abs(geo.angle_diff_deg((course_true + 180) % 360,
                                              brg_from_thr))
            if dist_thr < LOC_RANGE_NM and off_axis < 40.0:
                # LOC: angular deviation about the localizer antenna,
                # placed on the extended centerline past the threshold.
                loc_lat, loc_lon = geo.destination(
                    thr_lat, thr_lon, course_true, 1.2)
                brg_to_loc = geo.bearing_deg(fdm.lat_deg, fdm.lon_deg,
                                             loc_lat, loc_lon)
                # aircraft left of course -> bearing right of course ->
                # positive deviation = fly right (CDI convention)
                loc_dev = geo.angle_diff_deg(brg_to_loc, course_true)
                radio.ils_loc_dots = max(-2.5, min(2.5, loc_dev / LOC_DOT_DEG))

                # GS: elevation angle from the GS antenna
                gs_lat, gs_lon = geo.destination(
                    thr_lat, thr_lon, course_true, GS_ANTENNA_NM)
                d_gs_nm = geo.dist_nm(fdm.lat_deg, fdm.lon_deg, gs_lat, gs_lon)
                height_ft = fdm.alt_ft - (fms.appr_thr_elev_ft + TCH_FT)
                if d_gs_nm > 0.05:
                    angle = math.degrees(math.atan2(height_ft,
                                                    d_gs_nm * 6076.12))
                    gs_dev = angle - fms.appr_gs_deg  # + = above path
                    radio.ils_gs_dots = max(-2.5, min(2.5,
                                                      gs_dev / GS_DOT_DEG))
                radio.ils_ok = True
                radio.ils_ident = fms.appr_ident
                radio.ils_course_mag = fms.appr_course_mag
                radio.ils_dme_nm = round(dist_thr, 1)
