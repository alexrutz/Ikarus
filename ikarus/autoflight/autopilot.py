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


def angle_diff_deg(target: float, current: float) -> float:
    """Shortest signed angular difference target-current in (-180, 180]."""
    d = (target - current) % 360.0
    return d - 360.0 if d > 180.0 else d


class OuterLoops:
    def __init__(self, state: SimState):
        self.state = state
        self._soe_int = 0.0

    def sync(self) -> None:
        g, fdm = self.state.guidance, self.state.fdm
        g.pitch_target_deg = fdm.pitch_deg
        g.roll_target_deg = 0.0
        self._soe_int = 0.0

    def update(self, dt: float, modes: ModeLogic) -> None:
        state = self.state
        g, fcu, fdm = state.guidance, state.fcu, state.fdm

        # Resolve the A/THR speed target: in Mach mode the window holds a
        # Mach number (< 1.0), converted via the current CAS/Mach ratio.
        if fcu.spd_is_mach and fcu.spd_kts < 1.0 and fdm.mach > 0.05:
            g.target_cas_kts = fcu.spd_kts * (fdm.cas_kts / fdm.mach)
        else:
            g.target_cas_kts = fcu.spd_kts

        # --- lateral -----------------------------------------------------------
        if modes.lat_active == "HDG":
            hdg_err = angle_diff_deg(fcu.hdg_deg, fdm.hdg_true_deg)
            g.roll_target_deg = clamp(HDG_KP * hdg_err,
                                      -BANK_LIMIT_DEG, BANK_LIMIT_DEG)

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
        elif mode in ("OP CLB", "OP DES"):
            self._fly_speed_on_elevator(mode, dt)

    def _fly_vs(self, vs_target: float, dt: float) -> None:
        """Path mode: pitch = gamma feedforward + alpha + residual."""
        g, fdm = self.state.guidance, self.state.fdm
        tas_fpm = max(fdm.tas_kts, 120.0) * KTS_TO_FPM
        gamma_tgt = math.degrees(math.asin(clamp(vs_target / tas_fpm, -0.35, 0.35)))
        vs_err = vs_target - fdm.vs_fpm
        raw = clamp(gamma_tgt + fdm.alpha_deg + VS_RESIDUAL_KP * vs_err,
                    PITCH_TARGET_LIMIT_DN, PITCH_TARGET_LIMIT_UP)
        self._slew_pitch(raw, dt)

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
