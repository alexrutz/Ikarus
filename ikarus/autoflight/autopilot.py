"""Autoflight outer loops: active modes -> pitch/roll attitude targets.

Pure guidance computation, written into GuidanceState each tick. The FD
bars display these targets; the FBW inner loop flies them when the AP
is engaged.
"""

from __future__ import annotations

import math

from ikarus.autoflight.control_laws import clamp
from ikarus.autoflight.modes import ModeLogic
from ikarus.core.state import SimState
from ikarus.nav import geo

BANK_LIMIT_DEG = 25.0
HDG_KP = 1.2                 # deg bank per deg heading error
VS_LIMIT_FPM = 2400.0        # V/S profile limit in path modes
ALT_TO_VS = 4.0              # fpm per ft of altitude error
VS_RESIDUAL_KP = 0.0008      # deg of extra pitch per fpm of V/S error
PITCH_TARGET_LIMIT_UP = 18.0
PITCH_TARGET_LIMIT_DN = -10.0
PITCH_TARGET_SLEW_DEG_S = 1.5
KTS_TO_FPM = 101.2686

# speed-on-elevator (OP CLB / OP DES) gains
SOE_KP = 0.20                # deg pitch per kt of speed error
SOE_KI = 0.035
SOE_INT_LIMIT = 12.0
OP_VS_FLOOR_FPM = 100.0      # OP CLB never descends / OP DES never climbs

# LOC/GS tracking gains
LOC_INTERCEPT_PER_DOT = 12.0  # deg of track cut per dot of deviation
LOC_TAE_KP = 1.6
LOC_BANK_LIMIT = 25.0
GS_VS_PER_DOT = 350.0         # fpm of correction per dot of G/S deviation
GS_INT_FPM_PER_DOT_S = 30.0   # integral: kills standing beam offset
GS_INT_LIMIT_FPM = 800.0
KTS_TO_FPS = 1.68781

# managed descent
DES_VDEV_VS_GAIN = 1.2        # fpm of extra V/S per ft of profile deviation
DES_MAX_VS_FPM = 3200.0
DES_MIN_VS_FPM = 700.0


def angle_diff_deg(target: float, current: float) -> float:
    """Shortest signed angular difference target-current in (-180, 180]."""
    d = (target - current) % 360.0
    return d - 360.0 if d > 180.0 else d


class OuterLoops:
    ALPHA_FILTER_TAU_S = 4.0   # low-pass on alpha feedforward (breaks the
                               # phugoid feedback through measured alpha)

    def __init__(self, state: SimState):
        self.state = state
        self._soe_int = 0.0
        self._gs_int_fpm = 0.0
        self._alpha_f: float | None = None

    def sync(self) -> None:
        g, fdm = self.state.guidance, self.state.fdm
        g.pitch_target_deg = fdm.pitch_deg
        g.roll_target_deg = 0.0
        self._soe_int = 0.0
        self._gs_int_fpm = 0.0
        self._alpha_f = None

    def _alpha_filtered(self, dt: float) -> float:
        alpha = self.state.fdm.alpha_deg
        if self._alpha_f is None:
            self._alpha_f = alpha
        else:
            self._alpha_f += (alpha - self._alpha_f) * dt / self.ALPHA_FILTER_TAU_S
        return self._alpha_f

    def update(self, dt: float, modes: ModeLogic) -> None:
        state = self.state
        g, fcu, fdm = state.guidance, state.fcu, state.fdm

        # Resolve the A/THR speed target: in Mach mode the window holds a
        # Mach number (< 1.0), converted via the current CAS/Mach ratio.
        if fcu.spd_is_mach and fcu.spd_kts < 1.0 and fdm.mach > 0.05:
            g.target_cas_kts = fcu.spd_kts * (fdm.cas_kts / fdm.mach)
        else:
            g.target_cas_kts = fcu.spd_kts

        # managed speed target when the FCU speed is pushed (managed)
        if fcu.spd_managed and state.fms.nav_ok:
            g.target_cas_kts = state.fms.managed_spd_kts

        # --- lateral -----------------------------------------------------------
        lat = modes.lat_active
        if lat == "HDG":
            hdg_err = angle_diff_deg(fcu.hdg_deg, fdm.hdg_true_deg)
            g.roll_target_deg = clamp(HDG_KP * hdg_err,
                                      -BANK_LIMIT_DEG, BANK_LIMIT_DEG)
        elif lat == "NAV" and state.fms.nav_ok:
            g.roll_target_deg = state.fms.nav_roll_cmd_deg
        elif lat in ("LOC*", "LOC") and state.radio.ils_ok:
            radio = state.radio
            course_true = (radio.ils_course_mag
                           + geo.magvar_deg(fdm.lat_deg, fdm.lon_deg)) % 360.0
            cut = clamp(radio.ils_loc_dots * LOC_INTERCEPT_PER_DOT,
                        -45.0, 45.0)
            desired_track = (course_true + cut) % 360.0
            tae = angle_diff_deg(desired_track, fdm.track_true_deg)
            g.roll_target_deg = clamp(LOC_TAE_KP * tae,
                                      -LOC_BANK_LIMIT, LOC_BANK_LIMIT)

        # --- vertical ----------------------------------------------------------
        mode = modes.vert_active
        if mode in ("ALT", "ALT*", "V/S"):
            alt_err = fcu.alt_ft - fdm.alt_ft
            if mode == "V/S":
                vs_target = fcu.vs_fpm or 0.0
            else:
                vs_target = clamp(alt_err * ALT_TO_VS,
                                  -VS_LIMIT_FPM, VS_LIMIT_FPM)
            self._fly_vs(vs_target, dt)
            self._soe_int = 0.0
        elif mode in ("OP CLB", "CLB"):
            self._fly_managed_climb(mode, dt, modes)
        elif mode == "OP DES":
            self._fly_speed_on_elevator("OP DES", dt)
        elif mode == "DES":
            self._fly_managed_descent(dt)
        elif mode in ("G/S*", "G/S") and state.radio.ils_ok:
            # V/S to hold the glide path: proportional + integral on the
            # deviation (the integral removes the standing beam offset
            # the V/S feedforward alone leaves)
            dots = state.radio.ils_gs_dots
            self._gs_int_fpm = clamp(
                self._gs_int_fpm + dots * GS_INT_FPM_PER_DOT_S * dt,
                -GS_INT_LIMIT_FPM, GS_INT_LIMIT_FPM)
            gs_kts = max(fdm.gs_kts, 100.0)
            path_vs = -math.tan(math.radians(state.fms.appr_gs_deg)) \
                * gs_kts * KTS_TO_FPS * 60.0
            vs_target = path_vs - dots * GS_VS_PER_DOT - self._gs_int_fpm
            self._fly_vs(vs_target, dt)
            self._soe_int = 0.0
        if mode not in ("G/S*", "G/S"):
            self._gs_int_fpm = 0.0

    def _fly_vs(self, vs_target: float, dt: float) -> None:
        """Path mode: pitch = gamma feedforward + alpha + small residual.

        No integrator here: modes with an outer loop (ALT, G/S) remove
        standing errors themselves; adding one at this level couples
        into the phugoid and hunts.
        """
        g, fdm = self.state.guidance, self.state.fdm
        tas_fpm = max(fdm.tas_kts, 120.0) * KTS_TO_FPM
        gamma_tgt = math.degrees(math.asin(clamp(vs_target / tas_fpm, -0.35, 0.35)))
        vs_err = vs_target - fdm.vs_fpm
        raw = clamp(gamma_tgt + self._alpha_filtered(dt)
                    + VS_RESIDUAL_KP * vs_err,
                    PITCH_TARGET_LIMIT_DN, PITCH_TARGET_LIMIT_UP)
        self._slew_pitch(raw, dt)

    def _fly_managed_climb(self, mode: str, dt: float,
                           modes: ModeLogic) -> None:
        """CLB: open climb but leveling at at-or-below constraints."""
        state = self.state
        fdm, fcu = state.fdm, state.fcu
        constraint = state.fms.clb_constraint_ft if mode == "CLB" else None
        if constraint is not None and constraint < fcu.alt_ft \
                and fdm.alt_ft > constraint - 300:
            # level off at the constraint until it sequences away
            alt_err = constraint - fdm.alt_ft
            self._fly_vs(clamp(alt_err * ALT_TO_VS,
                               -VS_LIMIT_FPM, VS_LIMIT_FPM), dt)
            self._soe_int = 0.0
        else:
            self._fly_speed_on_elevator("OP CLB", dt)

    def _fly_managed_descent(self, dt: float) -> None:
        """DES: fly the geometric profile via V/S, idle when high."""
        state = self.state
        fdm, fms, fcu = state.fdm, state.fms, state.fcu
        gs_kts = max(fdm.gs_kts, 100.0)
        path_vs = -318.0 * gs_kts / 60.0  # profile gradient at current GS
        vs_target = path_vs - clamp(fms.vdev_ft * DES_VDEV_VS_GAIN,
                                    -1500.0, 2000.0)
        vs_target = clamp(vs_target, -DES_MAX_VS_FPM, -DES_MIN_VS_FPM)
        # never descend below the FCU altitude
        if fdm.alt_ft < fcu.alt_ft + 150:
            vs_target = clamp((fcu.alt_ft - fdm.alt_ft) * ALT_TO_VS,
                              -VS_LIMIT_FPM, VS_LIMIT_FPM)
        self._fly_vs(vs_target, dt)
        self._soe_int = 0.0

    def _fly_speed_on_elevator(self, mode: str, dt: float) -> None:
        """Fixed-thrust mode: pitch holds the target speed."""
        g, fdm = self.state.guidance, self.state.fdm
        err = fdm.cas_kts - g.target_cas_kts   # fast -> pitch up
        self._soe_int = clamp(self._soe_int + SOE_KI * err * dt,
                              -SOE_INT_LIMIT, SOE_INT_LIMIT)
        # base attitude = alpha (level pitch), speed error steers gamma
        raw = fdm.alpha_deg + SOE_KP * err + self._soe_int
        # never fly through level: OP CLB keeps climbing, OP DES descending
        tas_fpm = max(fdm.tas_kts, 120.0) * KTS_TO_FPM
        min_gamma = math.degrees(OP_VS_FLOOR_FPM / tas_fpm)
        if mode == "OP CLB":
            raw = max(raw, fdm.alpha_deg + min_gamma)
        else:
            raw = min(raw, fdm.alpha_deg - min_gamma)
        raw = clamp(raw, PITCH_TARGET_LIMIT_DN, PITCH_TARGET_LIMIT_UP)
        self._slew_pitch(raw, dt)

    def _slew_pitch(self, raw_target: float, dt: float) -> None:
        g = self.state.guidance
        step = clamp(raw_target - g.pitch_target_deg,
                     -PITCH_TARGET_SLEW_DEG_S * dt, PITCH_TARGET_SLEW_DEG_S * dt)
        g.pitch_target_deg += step
