"""FBW inner loop: attitude-command controller running at FDM rate.

M1 version: a straightforward attitude hold (pitch/roll targets in,
surface commands out) plus a yaw damper. M2 evolves this toward A320
normal law (C*-style pitch, roll rate command, protections).

Sign conventions (verified against the stock model):
- positive aileron command rolls right
- negative elevator command pitches up
- positive values of ``AutopilotState.pitch_target_deg`` mean nose up.

The stock model's FCS provides its own yaw damper (yaw-rate and beta
feedback summed into the rudder), so no yaw damping is added here —
doing so caused an actuator-lag limit cycle.
"""

from __future__ import annotations

from ikarus.core.fdm import JsbsimAdapter
from ikarus.core.state import SimState

RAD_TO_DEG = 57.29577951308232


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class InnerLoop:
    """Closes pitch/roll/yaw loops every FDM step (120 Hz)."""

    # Pitch attitude PID (per deg error / deg-per-sec rate)
    PITCH_KP = 0.06
    PITCH_KI = 0.025
    PITCH_KD = 0.11
    PITCH_INT_LIMIT = 12.0
    # Roll attitude PD
    ROLL_KP = 0.035
    ROLL_KD = 0.020

    def __init__(self) -> None:
        self._pitch_int = 0.0

    def reset(self) -> None:
        self._pitch_int = 0.0

    def update(self, state: SimState, adapter: JsbsimAdapter, dt: float) -> None:
        fdm = state.fdm
        ap = state.ap

        # --- pitch ---------------------------------------------------------
        err = ap.pitch_target_deg - fdm.pitch_deg
        self._pitch_int = clamp(self._pitch_int + err * dt,
                                -self.PITCH_INT_LIMIT, self.PITCH_INT_LIMIT)
        q_deg = fdm.q_rps * RAD_TO_DEG
        u = (self.PITCH_KP * err
             + self.PITCH_KI * self._pitch_int
             - self.PITCH_KD * q_deg)
        adapter.set_elevator(clamp(-u, -1.0, 1.0))

        # --- roll ----------------------------------------------------------
        roll_err = ap.roll_target_deg - fdm.roll_deg
        p_deg = fdm.p_rps * RAD_TO_DEG
        aileron = self.ROLL_KP * roll_err - self.ROLL_KD * p_deg
        adapter.set_aileron(clamp(aileron, -1.0, 1.0))

        # --- yaw ------------------------------------------------------------
        # The stock A320 FCS already sums a yaw damper (r and beta feedback)
        # into the rudder, so only the pilot's input is passed through here.
        adapter.set_rudder(clamp(0.3 * state.ctl.rudder_input, -1.0, 1.0))
