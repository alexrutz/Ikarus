"""Provisional M1 autopilot: HDG / ALT (via V/S profile) / SPD holds.

Runs as a system at SYSTEMS_HZ and produces the same pitch/roll attitude
targets the FBW inner loop consumes — engaging the AP just replaces the
pilot as the source of attitude targets, exactly the architecture the
real mode logic takes over in M2.

Vertical control uses flight-path-angle feedforward: the pitch that
produces a wanted V/S is (gamma_target + alpha), so the outer loop
commands that attitude directly and only trims the residual with a small
gain — far more stable than integrating V/S error into a pitch rate.
"""

from __future__ import annotations

import math

from ikarus.autoflight.control_laws import clamp
from ikarus.systems.base import System

BANK_LIMIT_DEG = 25.0
HDG_KP = 1.2                 # deg bank per deg heading error
VS_LIMIT_FPM = 2400.0
ALT_TO_VS = 4.0              # fpm commanded per ft of altitude error
VS_RESIDUAL_KP = 0.0008      # deg of extra pitch per fpm of V/S error
PITCH_TARGET_LIMIT = 15.0
PITCH_TARGET_SLEW_DEG_S = 1.5
ALT_CAPTURE_BAND_FT = 20.0

THR_KP = 0.015               # throttle per kt of speed error
THR_KI = 0.004


def angle_diff_deg(target: float, current: float) -> float:
    """Shortest signed angular difference target-current in (-180, 180]."""
    d = (target - current) % 360.0
    return d - 360.0 if d > 180.0 else d


class SimpleAutopilot(System):
    name = "autopilot"

    def __init__(self) -> None:
        super().__init__()
        self._thr_int = 0.6

    def init_situation(self, situation: str) -> None:
        ap, fdm = self.state.ap, self.state.fdm
        # Sync targets to the current state so engagement is bumpless.
        ap.sel_hdg_deg = round(fdm.hdg_true_deg)
        ap.sel_alt_ft = round(fdm.alt_ft / 100) * 100
        ap.sel_spd_kts = round(fdm.cas_kts)
        ap.pitch_target_deg = fdm.pitch_deg
        ap.roll_target_deg = 0.0
        if situation == "cruise":
            ap.ap_engaged = True
            ap.athr_engaged = True
        else:
            ap.ap_engaged = False
            ap.athr_engaged = False
        self._thr_int = self.state.ctl.thrust_lever

    def update(self, dt: float) -> None:
        ap, fdm = self.state.ap, self.state.fdm

        if ap.ap_engaged:
            # Lateral: heading hold/select.
            hdg_err = angle_diff_deg(ap.sel_hdg_deg, fdm.hdg_true_deg)
            ap.roll_target_deg = clamp(HDG_KP * hdg_err,
                                       -BANK_LIMIT_DEG, BANK_LIMIT_DEG)

            # Vertical: fly a V/S profile toward the selected altitude.
            alt_err = ap.sel_alt_ft - fdm.alt_ft
            vs_target = clamp(alt_err * ALT_TO_VS, -VS_LIMIT_FPM, VS_LIMIT_FPM)
            if ap.sel_vs_fpm and abs(alt_err) > 500.0:
                # Pilot-selected V/S applies until altitude capture.
                if (ap.sel_vs_fpm > 0) == (alt_err > 0):
                    vs_target = clamp(ap.sel_vs_fpm,
                                      -abs(vs_target), abs(vs_target)) \
                        if abs(ap.sel_vs_fpm) > abs(vs_target) else ap.sel_vs_fpm
            if abs(alt_err) < ALT_CAPTURE_BAND_FT and abs(fdm.vs_fpm) < 300:
                ap.sel_vs_fpm = 0.0

            # Feedforward: pitch = gamma_target + alpha, plus small residual.
            tas_fpm = max(fdm.tas_kts, 120.0) * 101.269  # kts -> ft/min
            gamma_tgt_deg = math.degrees(math.asin(
                clamp(vs_target / tas_fpm, -0.35, 0.35)))
            vs_err = vs_target - fdm.vs_fpm
            raw_target = clamp(gamma_tgt_deg + fdm.alpha_deg
                               + VS_RESIDUAL_KP * vs_err,
                               -PITCH_TARGET_LIMIT, PITCH_TARGET_LIMIT)
            # Slew-limit so target changes stay inside inner-loop bandwidth.
            step = clamp(raw_target - ap.pitch_target_deg,
                         -PITCH_TARGET_SLEW_DEG_S * dt,
                         PITCH_TARGET_SLEW_DEG_S * dt)
            ap.pitch_target_deg += step

        if ap.athr_engaged:
            spd_err = ap.sel_spd_kts - fdm.cas_kts
            self._thr_int = clamp(self._thr_int + THR_KI * spd_err * dt, 0.0, 1.0)
            thr = clamp(self._thr_int + THR_KP * spd_err, 0.0, 1.0)
            for i in range(self.adapter.n_engines):
                self.adapter.set_throttle(i, thr)
