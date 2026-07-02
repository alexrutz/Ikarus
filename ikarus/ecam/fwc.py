"""Flight Warning Computer: phases, alert evaluation, master warn/caution."""

from __future__ import annotations

from ikarus.ecam import alerts as alert_table
from ikarus.core.state import EcamAlert
from ikarus.systems.base import System


class FwcSystem(System):
    name = "fwc"

    def __init__(self) -> None:
        super().__init__()
        self._warning_latched = False
        self._prev_alert_ids: set[str] = set()

    def init_situation(self, situation: str) -> None:
        ecam = self.state.ecam
        ecam.cleared_ids = []
        self._warning_latched = False

    # commands ----------------------------------------------------------------

    def clear_key(self) -> None:
        """ECAM CLR: acknowledge/hide the top alert."""
        ecam = self.state.ecam
        for alert in ecam.alerts:
            if alert.id not in ecam.cleared_ids:
                ecam.cleared_ids.append(alert.id)
                return

    def recall_key(self) -> None:
        self.state.ecam.cleared_ids = []

    def cancel_warning(self) -> None:
        self._warning_latched = False

    # update --------------------------------------------------------------------

    def _flight_phase(self) -> int:
        """Simplified FWC phases: 1 elec on gnd, 2 eng start/taxi,
        3 takeoff power, 4 airborne low, 5 cruise, 6 approach, 7 rollout."""
        s = self.state
        if s.fdm.wow:
            if not any(s.eng.running):
                return 1
            if s.ctl.thrust_detent in ("FLX", "TOGA"):
                return 3
            return 2 if s.fdm.gs_kts < 45 else 7
        if s.fdm.agl_ft < 1500:
            return 4 if s.fdm.vs_fpm > -200 else 6
        return 5

    def update(self, dt: float) -> None:
        s = self.state
        ecam = s.ecam

        # no electrical power = no FWC (dark cockpit)
        if not (s.elec.ac1 or s.elec.ac2 or s.elec.dc_bat or s.elec.dc_ess):
            ecam.alerts = []
            ecam.memos = []
            ecam.master_warning = ecam.master_caution = False
            self._warning_latched = False
            self._prev_alert_ids = set()
            return

        ecam.flight_phase = self._flight_phase()

        active: list[EcamAlert] = []
        for alert in alert_table.ALERTS:
            if ecam.flight_phase in alert.inhibit_phases:
                continue
            try:
                sensed = alert.condition(s)
            except Exception:
                sensed = False
            if sensed:
                active.append(EcamAlert(
                    id=alert.id, level=alert.level,
                    lines=[list(line) for line in alert.lines],
                    sd_page=alert.sd_page))
        active.sort(key=lambda a: -a.level)
        ecam.alerts = active

        ids = {a.id for a in active}
        # drop stale cleared entries so alerts re-appear if they recur
        ecam.cleared_ids = [i for i in ecam.cleared_ids if i in ids]

        new_ids = ids - self._prev_alert_ids
        self._prev_alert_ids = ids
        if any(a.level == 3 and a.id in new_ids for a in active):
            self._warning_latched = True
        if not any(a.level == 3 for a in active):
            self._warning_latched = False

        ecam.master_warning = self._warning_latched
        ecam.master_caution = any(
            a.level == 2 and a.id not in ecam.cleared_ids for a in active)
        ecam.memos = [list(m) for m in alert_table.memos(s)]
