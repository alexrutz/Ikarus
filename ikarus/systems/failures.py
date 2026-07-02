"""Failure injection: a flag registry systems consult each tick.

Adding a failure = adding a catalog entry and one `failures.active(...)`
check in the owning system. Injected via the `failure.set` command
(UI page, tests, scripted scenarios).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureDef:
    id: str
    label: str
    description: str


CATALOG: list[FailureDef] = [
    FailureDef("ENG1_FLAMEOUT", "ENG 1 FLAMEOUT", "Engine 1 flames out"),
    FailureDef("ENG2_FLAMEOUT", "ENG 2 FLAMEOUT", "Engine 2 flames out"),
    FailureDef("ELEC_GEN1", "GEN 1 FAULT", "Generator 1 trips off"),
    FailureDef("ELEC_GEN2", "GEN 2 FAULT", "Generator 2 trips off"),
    FailureDef("HYD_G_LEAK", "GREEN HYD LEAK", "Green reservoir drains"),
    FailureDef("HYD_B_LEAK", "BLUE HYD LEAK", "Blue reservoir drains"),
    FailureDef("HYD_Y_LEAK", "YELLOW HYD LEAK", "Yellow reservoir drains"),
    FailureDef("ELAC1", "ELAC 1 FAULT", "ELAC 1 computer failure"),
    FailureDef("ELAC2", "ELAC 2 FAULT", "ELAC 2 computer failure"),
    FailureDef("SEC1", "SEC 1 FAULT", "SEC 1 computer failure"),
    FailureDef("SEC2", "SEC 2 FAULT", "SEC 2 computer failure"),
    FailureDef("SEC3", "SEC 3 FAULT", "SEC 3 computer failure"),
    FailureDef("BLEED1", "BLEED 1 FAULT", "Engine 1 bleed valve fails"),
    FailureDef("BLEED2", "BLEED 2 FAULT", "Engine 2 bleed valve fails"),
    FailureDef("PACK1", "PACK 1 FAULT", "Pack 1 stops"),
    FailureDef("PACK2", "PACK 2 FAULT", "Pack 2 stops"),
]

_IDS = {f.id for f in CATALOG}


class FailureManager:
    def __init__(self) -> None:
        self._active: set[str] = set()

    def set(self, failure_id: str, active: bool = True) -> None:
        if failure_id not in _IDS:
            raise KeyError(f"unknown failure {failure_id!r}")
        if active:
            self._active.add(failure_id)
        else:
            self._active.discard(failure_id)

    def active(self, failure_id: str) -> bool:
        return failure_id in self._active

    def clear_all(self) -> None:
        self._active.clear()

    @property
    def active_ids(self) -> list[str]:
        return sorted(self._active)
