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

THRUST_DETENTS = ("IDLE", "MAN", "CLB", "FLX", "TOGA")


class CommandError(Exception):
    pass


def _num(value, lo=None, hi=None) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise CommandError(f"numeric value required, got {value!r}")
    if lo is not None:
        v = clamp(v, lo, hi)
    return v


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
        sim = self._sim
        state = sim.state
        ctl, fcu, meta = state.ctl, state.fcu, state.sim
        modes = sim.systems.get("autoflight").modes

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

        def ctl_thrust_detent(v):
            if v not in THRUST_DETENTS:
                raise CommandError(f"detent must be one of {THRUST_DETENTS}")
            ctl.thrust_detent = v

        def ctl_thrust_manual(v):
            ctl.thrust_manual = _num(v, 0, 1)
            ctl.thrust_detent = "MAN"

        # --- FCU --------------------------------------------------------------
        def fcu_spd_set(v):
            val = _num(v)
            if val < 1.0:  # a Mach number
                fcu.spd_kts = clamp(val, 0.1, 0.85)
                fcu.spd_is_mach = True
            else:
                fcu.spd_kts = clamp(val, 100, 399)
                fcu.spd_is_mach = False

        def fcu_vs_set(v):
            fcu.vs_fpm = round(_num(v, -6000, 6000) / 100) * 100

        self._handlers.update({
            "sim.pause": sim_pause,
            "sim.accel": sim_accel,
            "ctl.pitch": ctl_pitch,
            "ctl.roll": ctl_roll,
            "ctl.rudder": ctl_rudder,
            "ctl.thrust.detent": ctl_thrust_detent,
            "ctl.thrust.manual": ctl_thrust_manual,
            "ctl.flaps": lambda v: setattr(ctl, "flaps_setting", int(_num(v, 0, 4))),
            "ctl.gear": lambda v: setattr(ctl, "gear_down", bool(v)),
            "ctl.speedbrake": lambda v: setattr(ctl, "speedbrake", _num(v, 0, 1)),
            "ctl.parking_brake": lambda v: setattr(ctl, "parking_brake", bool(v)),
            "fcu.spd.set": fcu_spd_set,
            "fcu.spd.push": lambda v: modes.spd_push(),
            "fcu.spd.pull": lambda v: modes.spd_pull(),
            "fcu.hdg.set": lambda v: setattr(fcu, "hdg_deg", _num(v, 0, 360) % 360),
            "fcu.hdg.push": lambda v: modes.hdg_push(),
            "fcu.hdg.pull": lambda v: modes.hdg_pull(),
            "fcu.alt.set": lambda v: setattr(fcu, "alt_ft",
                                             round(_num(v, 100, 41000) / 100) * 100),
            "fcu.alt.push": lambda v: modes.alt_push(),
            "fcu.alt.pull": lambda v: modes.alt_pull(),
            "fcu.vs.set": fcu_vs_set,
            "fcu.vs.push": lambda v: modes.vs_push(),
            "fcu.vs.pull": lambda v: modes.vs_pull(),
            "fcu.ap1.toggle": lambda v: modes.ap_toggle(v),
            "fcu.athr.toggle": lambda v: modes.athr_toggle(v),
            "fcu.fd.toggle": lambda v: setattr(
                fcu, "fd", (not fcu.fd) if v is None else bool(v)),
        })
