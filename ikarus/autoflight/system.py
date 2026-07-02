"""AutoflightSystem: orchestrates mode logic, outer loops and autothrust.

One System so the pieces run in a fixed order every tick:
modes (transitions) -> outer loops (targets) -> autothrust (throttles).
"""

from __future__ import annotations

from ikarus.autoflight.autopilot import OuterLoops
from ikarus.autoflight.autothrust import Autothrust
from ikarus.autoflight.modes import ModeLogic
from ikarus.core.fdm import JsbsimAdapter
from ikarus.core.state import SimState
from ikarus.systems.base import System


class AutoflightSystem(System):
    name = "autoflight"

    def __init__(self) -> None:
        super().__init__()
        self.modes: ModeLogic = None  # type: ignore[assignment]
        self.outer: OuterLoops = None  # type: ignore[assignment]
        self.athr: Autothrust = None  # type: ignore[assignment]

    def bind(self, state: SimState, adapter: JsbsimAdapter,
             failures) -> None:
        super().bind(state, adapter, failures)
        self.modes = ModeLogic(state)
        self.outer = OuterLoops(state)
        self.athr = Autothrust(state, adapter)

    def init_situation(self, situation: str) -> None:
        fcu, fdm, ctl = self.state.fcu, self.state.fdm, self.state.ctl
        fcu.hdg_deg = round(fdm.hdg_true_deg) % 360
        fcu.alt_ft = round(fdm.alt_ft / 100) * 100
        fcu.spd_kts = max(round(fdm.cas_kts), 100)
        fcu.vs_fpm = None
        self.outer.sync()
        if situation == "cruise":
            fcu.ap1 = True
            fcu.athr = True
            fcu.fd = True
            ctl.thrust_detent = "CLB"
            self.modes.lat_active = "HDG"
            self.modes.vert_active = "ALT"
            self.athr.sync(0.6)
        else:  # runway / cold_dark
            fcu.ap1 = False
            fcu.athr = False
            fcu.fd = True
            fcu.alt_ft = 5000.0
            fcu.spd_kts = 250.0
            ctl.thrust_detent = "IDLE"
            self.athr.sync(0.0)

    def update(self, dt: float) -> None:
        self.modes.update()
        self.outer.update(dt, self.modes)
        self.athr.update(dt, self.modes.athr_mode)
