"""System framework: base class and ordered manager.

Systems communicate only by reading each other's SimState sections;
direct references between systems are forbidden so any section can be
fabricated in tests. Update order is an explicit list — it encodes the
physical dependency chain (power before pumps, bleed before start).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ikarus.core.fdm import JsbsimAdapter
from ikarus.core.state import SimState


class System(ABC):
    """A simulated aircraft (or avionics) system ticked at SYSTEMS_HZ."""

    name: str = "system"

    def __init__(self) -> None:
        self.state: SimState = None  # type: ignore[assignment]
        self.adapter: JsbsimAdapter = None  # type: ignore[assignment]

    def bind(self, state: SimState, adapter: JsbsimAdapter) -> None:
        self.state = state
        self.adapter = adapter

    def init_situation(self, situation: str) -> None:
        """Set internal state for 'cruise', 'runway' or 'cold_dark'."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance the system by dt seconds (called at SYSTEMS_HZ)."""


class SystemManager:
    def __init__(self, systems: list[System]) -> None:
        self.systems = systems
        self._by_name = {s.name: s for s in systems}

    def bind(self, state: SimState, adapter: JsbsimAdapter) -> None:
        for s in self.systems:
            s.bind(state, adapter)

    def init_situation(self, situation: str) -> None:
        for s in self.systems:
            s.init_situation(situation)

    def update(self, dt: float) -> None:
        for s in self.systems:
            s.update(dt)

    def get(self, name: str) -> System:
        return self._by_name[name]
