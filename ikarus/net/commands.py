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
            "fcu.loc.toggle": lambda v: modes.loc_toggle(),
            "fcu.appr.toggle": lambda v: modes.appr_toggle(),
            "mcdu.key": lambda v: sim.systems.get("fms").mcdu.key(v or ""),
            "radio.nav1.set": lambda v: setattr(
                state.radio, "nav1_freq_khz", _num(v, 0, 118000)),
            "radio.nav2.set": lambda v: setattr(
                state.radio, "nav2_freq_khz", _num(v, 0, 118000)),
        })

        # --- overhead panel: boolean switches map straight onto state ------
        bool_switches = {
            "ovhd.elec.bat1": (state.elec, "bat1"),
            "ovhd.elec.bat2": (state.elec, "bat2"),
            "ovhd.elec.ext_pwr": (state.elec, "ext_pwr"),
            "ovhd.elec.gen1": (state.elec, "gen1"),
            "ovhd.elec.gen2": (state.elec, "gen2"),
            "ovhd.elec.apu_gen": (state.elec, "apu_gen"),
            "ovhd.elec.bus_tie": (state.elec, "bus_tie"),
            "ovhd.apu.master": (state.apu, "master"),
            "ovhd.apu.start": (state.apu, "start_pb"),
            "ovhd.fuel.pump_l1": (state.fuel, "pump_l1"),
            "ovhd.fuel.pump_l2": (state.fuel, "pump_l2"),
            "ovhd.fuel.pump_c1": (state.fuel, "pump_c1"),
            "ovhd.fuel.pump_c2": (state.fuel, "pump_c2"),
            "ovhd.fuel.pump_r1": (state.fuel, "pump_r1"),
            "ovhd.fuel.pump_r2": (state.fuel, "pump_r2"),
            "ovhd.fuel.xfeed": (state.fuel, "xfeed"),
            "ovhd.hyd.eng1_pump": (state.hyd, "eng1_pump"),
            "ovhd.hyd.eng2_pump": (state.hyd, "eng2_pump"),
            "ovhd.hyd.blue_elec": (state.hyd, "blue_elec_pump"),
            "ovhd.hyd.yellow_elec": (state.hyd, "yellow_elec_pump"),
            "ovhd.hyd.ptu": (state.hyd, "ptu_auto"),
            "ovhd.bleed.eng1": (state.bleed, "eng1_bleed"),
            "ovhd.bleed.eng2": (state.bleed, "eng2_bleed"),
            "ovhd.bleed.apu": (state.bleed, "apu_bleed"),
            "ovhd.bleed.pack1": (state.bleed, "pack1"),
            "ovhd.bleed.pack2": (state.bleed, "pack2"),
        }

        def make_bool_handler(obj, attr):
            def handler(v):
                setattr(obj, attr,
                        (not getattr(obj, attr)) if v is None else bool(v))
            return handler

        for name, (obj, attr) in bool_switches.items():
            self._handlers[name] = make_bool_handler(obj, attr)

        def ovhd_xbleed(v):
            if v not in ("AUTO", "OPEN", "SHUT"):
                raise CommandError("xbleed must be AUTO|OPEN|SHUT")
            state.bleed.xbleed = v

        def eng_master(i):
            def handler(v):
                state.eng.master[i] = bool(v) \
                    if v is not None else not state.eng.master[i]
            return handler

        def eng_mode(v):
            if v not in ("NORM", "IGN_START", "CRANK"):
                raise CommandError("mode must be NORM|IGN_START|CRANK")
            state.eng.mode = v

        fwc = sim.systems.get("fwc")
        sd = sim.systems.get("sd")
        self._handlers.update({
            "ovhd.bleed.xbleed": ovhd_xbleed,
            "eng.master1": eng_master(0),
            "eng.master2": eng_master(1),
            "eng.mode": eng_mode,
            "ecam.page": lambda v: sd.select_page(str(v or "")),
            "ecam.clr": lambda v: fwc.clear_key(),
            "ecam.rcl": lambda v: fwc.recall_key(),
            "ecam.warning_cancel": lambda v: fwc.cancel_warning(),
            "press.ldg_elev": lambda v: setattr(
                state.press, "ldg_elev_ft", _num(v, -1000, 15000)),
            "failure.set": make_failure_handler(sim, True),
            "failure.clear": make_failure_handler(sim, False),
            "failure.clear_all": lambda v: sim.failures.clear_all(),
        })


def make_failure_handler(sim, active: bool):
    def handler(v):
        try:
            sim.failures.set(str(v), active)
        except KeyError as e:
            raise CommandError(str(e))
    return handler
