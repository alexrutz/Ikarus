"""Pilot controls: applies inceptor state to the FDM, decays keyboard pulses.

Keyboard input arrives as pulses (ctl.pitch / ctl.roll commands add to the
input value); the input decays back to zero so a tap gives a nudge and
holding a key gives a sustained input. With the AP off, stick input slews
the attitude targets that the FBW inner loop holds — an attitude-command/
attitude-hold scheme, which is close to how the real FBW feels and is
friendly to discrete keyboard input.
"""

from __future__ import annotations

from ikarus.autoflight.control_laws import clamp
from ikarus.systems.base import System

INPUT_DECAY_PER_S = 2.5      # fraction of input removed per second
PITCH_SLEW_DEG_S = 6.0       # target slew at full stick
ROLL_SLEW_DEG_S = 15.0
MANUAL_PITCH_LIMIT = 25.0
MANUAL_ROLL_LIMIT = 45.0

# A320 flap lever positions -> JSBSim flap-cmd-norm
FLAP_POSITIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


class ControlsSystem(System):
    name = "controls"

    def init_situation(self, situation: str) -> None:
        ctl = self.state.ctl
        if situation == "cruise":
            ctl.gear_down = False
            ctl.flaps_setting = 0
            ctl.parking_brake = False
            ctl.thrust_lever = 0.6
        else:  # runway, cold_dark
            ctl.gear_down = True
            ctl.flaps_setting = 0
            ctl.parking_brake = True
            ctl.thrust_lever = 0.0

    def update(self, dt: float) -> None:
        ctl, ap, fdm = self.state.ctl, self.state.ap, self.state.fdm

        # Manual flight: stick input slews the attitude targets.
        if not ap.ap_engaged:
            ap.pitch_target_deg = clamp(
                ap.pitch_target_deg + ctl.pitch_input * PITCH_SLEW_DEG_S * dt,
                -MANUAL_PITCH_LIMIT, MANUAL_PITCH_LIMIT)
            ap.roll_target_deg = clamp(
                ap.roll_target_deg + ctl.roll_input * ROLL_SLEW_DEG_S * dt,
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

        # Manual thrust when A/THR is off.
        if not ap.athr_engaged:
            for i in range(self.adapter.n_engines):
                self.adapter.set_throttle(i, ctl.thrust_lever)
