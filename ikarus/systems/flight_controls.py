"""Flight-control computers and law selection.

ELAC/SEC/FAC availability follows their power buses (and injectable
failures in M5). Law: normal with any ELAC; alternate when both ELACs
are lost (or dual hydraulics); direct when in alternate with gear down.
The FBW inner loop consumes ``guidance.law``.
"""

from __future__ import annotations

from ikarus.systems.base import System


class FlightControlSystem(System):
    name = "flight_controls"

    def update(self, dt: float) -> None:
        fctl, e, hyd = self.state.fctl, self.state.elec, self.state.hyd

        fail = self.failures.active
        fctl.elac[0] = (e.ac_ess or e.dc_ess) and not fail("ELAC1")
        fctl.elac[1] = (e.ac2 or e.dc2) and not fail("ELAC2")
        fctl.sec[0] = (e.ac_ess or e.dc_ess) and not fail("SEC1")
        fctl.sec[1] = (e.ac2 or e.dc2) and not fail("SEC2")
        fctl.sec[2] = (e.ac1 or e.dc1) and not fail("SEC3")
        fctl.fac[0] = e.ac_ess or e.dc_ess
        fctl.fac[1] = e.ac2 or e.dc2

        # hydraulic-driven degradation only applies in flight — on the
        # ground with engines off, zero pressure is the normal state
        dual_hyd_lost = (not self.state.fdm.wow) and sum(p > 1450 for p in (
            hyd.green_press_psi, hyd.blue_press_psi,
            hyd.yellow_press_psi)) <= 1

        if any(fctl.elac) and not dual_hyd_lost:
            law = "normal"
        elif any(fctl.elac) or any(fctl.sec):
            # alternate law; degrades to direct with the gear down in flight
            law = "alternate"
            if self.state.ctl.gear_down and not self.state.fdm.wow:
                law = "direct"
        else:
            law = "direct"
        fctl.law = law
        self.state.guidance.law = law
