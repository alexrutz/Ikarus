"""Command registry: one dotted-name dispatch shared by UI, keyboard, tests.

Every user-initiated action goes through here so that behavior is
identical whether it comes from a WebSocket message, a pytest scenario,
or a scripted demo flight.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from ikarus.autoflight.control_laws import clamp

if TYPE_CHECKING:
    from ikarus.core.simloop import Sim


class CommandError(Exception):
    pass


class CommandRegistry:
    def __init__(self, sim: "Sim"):
        self._sim = sim
        self._handlers: dict[str, Callable] = {}
        self._register_defaults()

    def register(self, name: str, handler: Callable) -> None:
        self._handlers[name] = handler

    def dispatch(self, name: str, value=None) -> None:
        handler = self._handlers.get(name)
        if handler is None:
            raise CommandError(f"unknown command {name!r}")
        handler(value)

    @property
    def names(self) -> list[str]:
        return sorted(self._handlers)

    def _register_defaults(self) -> None:
        state = self._sim.state
        ctl, ap, meta = state.ctl, state.ap, state.sim

        def _num(value, lo=None, hi=None) -> float:
            try:
                v = float(value)
            except (TypeError, ValueError):
                raise CommandError(f"numeric value required, got {value!r}")
            if lo is not None:
                v = clamp(v, lo, hi)
            return v

        # --- sim control ----------------------------------------------------
        def sim_pause(v):
            meta.paused = bool(v) if v is not None else not meta.paused

        def sim_accel(v):
            accel = int(_num(v, 1, 4))
            meta.accel = min(a for a in (1, 2, 4) if a >= accel)

        # --- primary flight controls (keyboard pulses) ----------------------
        def ctl_pitch(v):
            ctl.pitch_input = clamp(ctl.pitch_input + _num(v, -1, 1), -1, 1)

        def ctl_roll(v):
            ctl.roll_input = clamp(ctl.roll_input + _num(v, -1, 1), -1, 1)

        def ctl_rudder(v):
            ctl.rudder_input = clamp(ctl.rudder_input + _num(v, -1, 1), -1, 1)

        def ctl_thrust(v):
            ctl.thrust_lever = _num(v, 0, 1)

        def ctl_flaps(v):
            ctl.flaps_setting = int(_num(v, 0, 4))

        def ctl_gear(v):
            ctl.gear_down = bool(v)

        def ctl_speedbrake(v):
            ctl.speedbrake = _num(v, 0, 1)

        def ctl_parking_brake(v):
            ctl.parking_brake = bool(v)

        # --- provisional autopilot (replaced by FCU commands in M2) ---------
        def ap_toggle(v):
            ap.ap_engaged = bool(v) if v is not None else not ap.ap_engaged
            if ap.ap_engaged:
                # Bumpless engagement: hold what the aircraft is doing now.
                ap.sel_hdg_deg = round(state.fdm.hdg_true_deg)
                ap.pitch_target_deg = state.fdm.pitch_deg

        def athr_toggle(v):
            ap.athr_engaged = bool(v) if v is not None else not ap.athr_engaged

        self._handlers.update({
            "sim.pause": sim_pause,
            "sim.accel": sim_accel,
            "ctl.pitch": ctl_pitch,
            "ctl.roll": ctl_roll,
            "ctl.rudder": ctl_rudder,
            "ctl.thrust": ctl_thrust,
            "ctl.flaps": ctl_flaps,
            "ctl.gear": ctl_gear,
            "ctl.speedbrake": ctl_speedbrake,
            "ctl.parking_brake": ctl_parking_brake,
            "ap.toggle": ap_toggle,
            "athr.toggle": athr_toggle,
            "ap.hdg.set": lambda v: setattr(ap, "sel_hdg_deg", _num(v, 0, 360) % 360),
            "ap.alt.set": lambda v: setattr(ap, "sel_alt_ft", _num(v, 100, 41000)),
            "ap.spd.set": lambda v: setattr(ap, "sel_spd_kts", _num(v, 100, 350)),
            "ap.vs.set": lambda v: setattr(ap, "sel_vs_fpm", _num(v, -6000, 6000)),
        })
