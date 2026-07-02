"""FBW inner loop: normal-law-style attitude control with protections.

Runs every FDM step (120 Hz). Consumes attitude targets — from the
autoflight guidance when the AP is engaged, from the sidestick targets
otherwise — and drives elevator/aileron/rudder.

Normal-law protections implemented (simplified):
- pitch attitude limits +30 / -15 deg
- bank angle: hard limit 67 deg, returns to 33 deg without input
- high-AoA: pitch target washed down when alpha exceeds alpha-prot
- load factor: pitch command reduced beyond +2.5 / -1 g
- high speed: nose-up bias above VMO/MMO

Law degradation (M5): 'alternate' drops the protections, 'direct' maps
stick straight to surfaces.

Sign conventions (verified against the stock model):
- positive aileron command rolls right
- negative elevator command pitches up

The stock model's FCS provides its own yaw damper (yaw-rate and beta
feedback summed into the rudder), so no yaw damping is added here —
doing so caused an actuator-lag limit cycle.
"""

from __future__ import annotations

from ikarus.core.fdm import JsbsimAdapter
from ikarus.core.state import SimState

RAD_TO_DEG = 57.29577951308232

# Protection thresholds
PITCH_MAX_DEG = 30.0
PITCH_MIN_DEG = -15.0
BANK_MAX_DEG = 67.0
BANK_NEUTRAL_DEG = 33.0
NZ_MAX = 2.5
NZ_MIN = -1.0
VMO_KTS = 350.0
MMO = 0.82
# alpha-prot per flap setting (clean .. full), simplified
ALPHA_PROT = (8.0, 11.0, 12.0, 13.0, 13.0)
ALPHA_GAIN = 2.5  # deg of pitch-down per deg of alpha beyond prot


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
        fdm, ctl, fcu = state.fdm, state.ctl, state.fcu
        law = state.guidance.law

        if fcu.ap1:
            pitch_tgt = state.guidance.pitch_target_deg
            roll_tgt = state.guidance.roll_target_deg
        else:
            pitch_tgt = ctl.pitch_target_deg
            roll_tgt = ctl.roll_target_deg

        if law == "normal":
            pitch_tgt, roll_tgt = self._apply_protections(
                state, pitch_tgt, roll_tgt, dt)

        if law == "direct":
            # stick straight to surfaces, no stabilization
            adapter.set_elevator(clamp(-ctl.pitch_input, -1.0, 1.0))
            adapter.set_aileron(clamp(ctl.roll_input, -1.0, 1.0))
            adapter.set_rudder(clamp(0.3 * ctl.rudder_input, -1.0, 1.0))
            return

        # --- pitch ---------------------------------------------------------
        err = pitch_tgt - fdm.pitch_deg
        self._pitch_int = clamp(self._pitch_int + err * dt,
                                -self.PITCH_INT_LIMIT, self.PITCH_INT_LIMIT)
        q_deg = fdm.q_rps * RAD_TO_DEG
        u = (self.PITCH_KP * err
             + self.PITCH_KI * self._pitch_int
             - self.PITCH_KD * q_deg)
        adapter.set_elevator(clamp(-u, -1.0, 1.0))

        # --- roll ----------------------------------------------------------
        roll_err = roll_tgt - fdm.roll_deg
        p_deg = fdm.p_rps * RAD_TO_DEG
        aileron = self.ROLL_KP * roll_err - self.ROLL_KD * p_deg
        adapter.set_aileron(clamp(aileron, -1.0, 1.0))

        # --- yaw ------------------------------------------------------------
        # Stock FCS carries the yaw damper; only pilot input passes through.
        adapter.set_rudder(clamp(0.3 * state.ctl.rudder_input, -1.0, 1.0))

    def _apply_protections(self, state: SimState, pitch_tgt: float,
                           roll_tgt: float, dt: float) -> tuple[float, float]:
        fdm, ctl, fcu = state.fdm, state.ctl, state.fcu

        # attitude limits
        pitch_tgt = clamp(pitch_tgt, PITCH_MIN_DEG, PITCH_MAX_DEG)
        roll_tgt = clamp(roll_tgt, -BANK_MAX_DEG, BANK_MAX_DEG)

        # bank returns to 33 deg without pilot input (manual flight only)
        if not fcu.ap1 and abs(roll_tgt) > BANK_NEUTRAL_DEG \
                and abs(ctl.roll_input) < 0.05:
            sign = 1.0 if roll_tgt > 0 else -1.0
            mag = max(BANK_NEUTRAL_DEG, abs(roll_tgt) - 5.0 * dt)
            roll_tgt = sign * mag
            ctl.roll_target_deg = roll_tgt

        # high-AoA protection
        alpha_prot = ALPHA_PROT[state.ctl.flaps_setting]
        if fdm.alpha_deg > alpha_prot:
            pitch_tgt = min(pitch_tgt,
                            fdm.pitch_deg
                            - (fdm.alpha_deg - alpha_prot) * ALPHA_GAIN)

        # load factor protection
        if fdm.nz_g > NZ_MAX - 0.2:
            pitch_tgt = min(pitch_tgt,
                            fdm.pitch_deg - (fdm.nz_g - (NZ_MAX - 0.2)) * 8.0)
        elif fdm.nz_g < NZ_MIN + 0.3:
            pitch_tgt = max(pitch_tgt,
                            fdm.pitch_deg + ((NZ_MIN + 0.3) - fdm.nz_g) * 8.0)

        # high speed protection: nose-up bias beyond VMO/MMO
        over_spd = max(fdm.cas_kts - (VMO_KTS + 4), 0.0) \
            + max((fdm.mach - (MMO + 0.006)) * 1000, 0.0)
        if over_spd > 0:
            pitch_tgt = max(pitch_tgt, fdm.pitch_deg + min(over_spd * 0.2, 6.0))

        return pitch_tgt, roll_tgt
