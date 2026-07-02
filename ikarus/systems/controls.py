"""Pilot controls: applies inceptor state to the FDM, decays keyboard pulses.

Keyboard input arrives as pulses (ctl.pitch / ctl.roll commands add to the
input value); the input decays back to zero so a tap gives a nudge and
holding a key gives a sustained input. With the AP off, stick input slews
the sidestick attitude targets that the FBW inner loop holds — an
attitude-command/attitude-hold scheme, close to how the real FBW feels
and friendly to discrete keyboard input.

Thrust is NOT applied here — the Autothrust component owns the throttles
every tick (levers act through it, including with A/THR off).
"""

from __future__ import annotations

from ikarus.autoflight.control_laws import clamp
from ikarus.systems.base import System

INPUT_DECAY_PER_S = 2.5      # fraction of input removed per second
PITCH_SLEW_DEG_S = 6.0       # target slew at full stick
ROLL_SLEW_DEG_S = 15.0
MANUAL_PITCH_LIMIT = 30.0    # protections clamp further in normal law
MANUAL_ROLL_LIMIT = 67.0

# A320 flap lever positions -> JSBSim flap-cmd-norm
FLAP_POSITIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


class ControlsSystem(System):
    name = "controls"

    def init_situation(self, situation: str) -> None:
        ctl, fdm = self.state.ctl, self.state.fdm
        ctl.pitch_target_deg = fdm.pitch_deg
        ctl.roll_target_deg = 0.0
        if situation == "cruise":
            ctl.gear_down = False
            ctl.flaps_setting = 0
            ctl.parking_brake = False
        else:  # runway, cold_dark
            ctl.gear_down = True
            ctl.flaps_setting = 0
            ctl.parking_brake = True

    def update(self, dt: float) -> None:
        ctl, fcu, fdm = self.state.ctl, self.state.fcu, self.state.fdm

        if fcu.ap1:
            # Track the AP so a later disconnect is bumpless.
            ctl.pitch_target_deg = fdm.pitch_deg
            ctl.roll_target_deg = fdm.roll_deg
        else:
            ctl.pitch_target_deg = clamp(
                ctl.pitch_target_deg + ctl.pitch_input * PITCH_SLEW_DEG_S * dt,
                -MANUAL_PITCH_LIMIT, MANUAL_PITCH_LIMIT)
            ctl.roll_target_deg = clamp(
                ctl.roll_target_deg + ctl.roll_input * ROLL_SLEW_DEG_S * dt,
                -MANUAL_ROLL_LIMIT, MANUAL_ROLL_LIMIT)

        # Keyboard pulses decay toward zero.
        decay = max(0.0, 1.0 - INPUT_DECAY_PER_S * dt)
        ctl.pitch_input *= decay
        ctl.roll_input *= decay
        ctl.rudder_input *= decay

        # Secondary controls straight through to the FDM.
        self.adapter.set_flaps(FLAP_POSITIONS[ctl.flaps_setting])
        self.adapter.set_gear(ctl.gear_down)
        self.adapter.set_speedbrake(ctl.speedbrake)
        self.adapter.set_brakes(1.0 if ctl.parking_brake and fdm.wow else 0.0)
