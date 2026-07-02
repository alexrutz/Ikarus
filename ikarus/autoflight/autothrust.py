"""Autothrust: resolves lever detents and A/THR modes into throttle commands.

The thrust levers set a ceiling (as on the real aircraft): with A/THR
active in SPEED/MACH the throttle servos between idle and the lever
detent; in THR CLB / THR IDLE the throttle is pinned. With A/THR off the
levers command thrust directly.
"""

from __future__ import annotations

from ikarus.autoflight.control_laws import clamp
from ikarus.core.fdm import JsbsimAdapter
from ikarus.core.state import SimState

DETENT_THROTTLE = {"IDLE": 0.0, "CLB": 0.88, "FLX": 0.95, "TOGA": 1.0}
SPD_KP = 0.015               # throttle per kt of speed error
SPD_KI = 0.004
THROTTLE_RATE_PER_S = 0.25   # servo rate limit


class Autothrust:
    def __init__(self, state: SimState, adapter: JsbsimAdapter):
        self.state = state
        self.adapter = adapter
        self._int = 0.6
        self._throttle = 0.6

    def sync(self, throttle: float) -> None:
        self._int = self._throttle = throttle

    def _lever_ceiling(self) -> float:
        ctl = self.state.ctl
        if ctl.thrust_detent == "MAN":
            return clamp(ctl.thrust_manual, 0.0, DETENT_THROTTLE["CLB"])
        return DETENT_THROTTLE[ctl.thrust_detent]

    def update(self, dt: float, athr_mode: str) -> None:
        fdm = self.state.fdm
        ceiling = self._lever_ceiling()

        if athr_mode in ("SPEED", "MACH"):
            err = self.state.guidance.target_cas_kts - fdm.cas_kts
            self._int = clamp(self._int + SPD_KI * err * dt, 0.0, ceiling)
            target = clamp(self._int + SPD_KP * err, 0.0, ceiling)
        elif athr_mode == "THR CLB":
            target = min(DETENT_THROTTLE["CLB"], ceiling)
            self._int = target
        elif athr_mode == "THR IDLE":
            target = 0.0
            self._int = 0.2
        else:
            # A/THR not active: levers command thrust directly.
            target = ceiling
            self._int = target

        step = clamp(target - self._throttle,
                     -THROTTLE_RATE_PER_S * dt, THROTTLE_RATE_PER_S * dt)
        self._throttle += step
        for i in range(self.adapter.n_engines):
            self.adapter.set_throttle(i, self._throttle)

    @property
    def throttle(self) -> float:
        return self._throttle
