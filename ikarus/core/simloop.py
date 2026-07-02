"""Sim facade and real-time loop.

`Sim` owns the adapter, state tree, systems and command registry and can
be ticked synchronously — `run_for()` is the fast-time mode all pytest
scenarios use. `SimLoop` wraps a Sim in wall-clock pacing for interactive
use (a fixed-timestep accumulator that drops debt rather than spiraling).
"""

from __future__ import annotations

import asyncio
import time

from ikarus import config
from ikarus.core.fdm import JsbsimAdapter
from ikarus.core.state import SimState
from ikarus.autoflight.control_laws import InnerLoop
from ikarus.autoflight.system import AutoflightSystem
from ikarus.ecam.fwc import FwcSystem
from ikarus.ecam.sd import SdSystem
from ikarus.fms.system import FmsSystem
from ikarus.nav.database import NavDatabase
from ikarus.nav.radio import RadioSystem
from ikarus.net.commands import CommandRegistry
from ikarus.systems.apu import ApuSystem
from ikarus.systems.base import SystemManager
from ikarus.systems.bleed import BleedSystem
from ikarus.systems.controls import ControlsSystem
from ikarus.systems.electrical import ElectricalSystem
from ikarus.systems.engines import EngineSystem
from ikarus.systems.flight_controls import FlightControlSystem
from ikarus.systems.fuel import FuelSystem
from ikarus.systems.hydraulics import HydraulicSystem
from ikarus.systems.pressurization import PressurizationSystem

TICK_S = 1.0 / config.SYSTEMS_HZ
FDM_DT = 1.0 / config.FDM_HZ


class Sim:
    def __init__(self, situation: str = "cruise"):
        self.adapter = JsbsimAdapter()
        self.state = SimState(fdm=self.adapter.state)
        self.state.sim.situation = situation
        self.inner_loop = InnerLoop()
        self.navdb = NavDatabase()
        # order = physical dependency chain (power -> pumps -> air -> ...)
        self.systems = SystemManager([
            ControlsSystem(),
            ElectricalSystem(),
            ApuSystem(),
            HydraulicSystem(),
            FuelSystem(),
            BleedSystem(),
            EngineSystem(),
            PressurizationSystem(),
            FlightControlSystem(),
            FmsSystem(self.navdb),
            RadioSystem(self.navdb),
            AutoflightSystem(),
            FwcSystem(),
            SdSystem(),
        ])
        self.systems.bind(self.state, self.adapter)
        self.commands = CommandRegistry(self)
        self._apply_situation(situation)

    def _apply_situation(self, situation: str) -> None:
        if situation == "cruise":
            self.adapter.init_cruise()
        elif situation in ("runway", "cold_dark"):
            self.adapter.init_runway(
                engines_running=(situation == "runway"))
        else:
            raise ValueError(f"unknown situation {situation!r}")
        self.inner_loop.reset()
        self.systems.init_situation(situation)

    def tick(self) -> None:
        """One systems tick: systems at SYSTEMS_HZ, FDM+FBW interleaved."""
        self.systems.update(TICK_S)
        for _ in range(config.FDM_STEPS_PER_SYSTEMS_TICK):
            self.inner_loop.update(self.state, self.adapter, FDM_DT)
            self.adapter.step()
        self.state.sim.time_s = self.state.fdm.sim_time_s

    def run_for(self, seconds: float) -> None:
        """Fast-time: run as fast as possible (test/scripting mode)."""
        for _ in range(round(seconds * config.SYSTEMS_HZ)):
            self.tick()

    def cmd(self, name: str, value=None) -> None:
        self.commands.dispatch(name, value)


class SimLoop:
    """Paces a Sim against the wall clock inside an asyncio loop."""

    POLL_S = 0.005

    def __init__(self, sim: Sim):
        self.sim = sim
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        acc = 0.0
        last = time.monotonic()
        while not self._stop.is_set():
            await asyncio.sleep(self.POLL_S)
            now = time.monotonic()
            meta = self.sim.state.sim
            if meta.paused:
                last = now
                acc = 0.0
                continue
            acc += (now - last) * meta.accel
            last = now
            if acc > config.MAX_TIME_DEBT_S:
                acc = TICK_S  # drop the debt, never spiral
            while acc >= TICK_S:
                self.sim.tick()
                acc -= TICK_S
