"""Fuel: 5 logical tanks (outer L/R, inner L/R, center) over the FDM's 2.

The logical tanks are the mass truth; each tick the burn measured from
the FDM tanks is applied to the logical tanks according to feed logic,
then the wing sums are written back so JSBSim carries the right mass.

Feed: inner-tank pumps feed their engine; center pumps override wing
feed when running (center-to-engine); crossfeed valve joins both sides.
Gravity feed keeps engines running with pumps off (no LO PR pressure).
Outer tanks auto-transfer into inners below a threshold.
"""

from __future__ import annotations

from ikarus.systems.base import System

OUTER_XFER_INNER_BELOW_LBS = 1650.0
OUTER_XFER_RATE_PPS = 30.0
LOW_LEVEL_LBS = 1650.0


class FuelSystem(System):
    name = "fuel"

    def __init__(self) -> None:
        super().__init__()
        self._last_fdm_total = None

    def init_situation(self, situation: str) -> None:
        f = self.state.fuel
        # split whatever the FDM was loaded with into the logical tanks
        total = self.state.fdm.total_fuel_lbs
        f.outer_l = f.outer_r = min(1500.0, total * 0.055)
        f.center = 0.0
        f.inner_l = f.inner_r = (total - 2 * f.outer_l) / 2
        f.total_lbs = total
        self._push_to_fdm()
        self._last_fdm_total = total
        if situation == "cold_dark":
            f.pump_l1 = f.pump_l2 = f.pump_r1 = f.pump_r2 = False
        else:
            f.pump_l1 = f.pump_l2 = f.pump_r1 = f.pump_r2 = True

    def _push_to_fdm(self) -> None:
        f = self.state.fuel
        # tank 0 = left wing aggregate, tank 1 = right wing aggregate;
        # center is split evenly into both FDM tanks for mass purposes
        self.adapter.set_tank_lbs(0, f.outer_l + f.inner_l + f.center / 2)
        self.adapter.set_tank_lbs(1, f.outer_r + f.inner_r + f.center / 2)

    def update(self, dt: float) -> None:
        f, e, eng = self.state.fuel, self.state.elec, self.state.eng

        # measured burn since last tick (JSBSim consumed from its tanks)
        fdm_total = self.state.fdm.total_fuel_lbs
        burn = max(0.0, (self._last_fdm_total or fdm_total) - fdm_total)

        # pump pressurization (pumps need AC power)
        l_pumps = (f.pump_l1 or f.pump_l2) and (e.ac1 or e.ac2)
        r_pumps = (f.pump_r1 or f.pump_r2) and (e.ac1 or e.ac2)
        c_pumps = (f.pump_c1 or f.pump_c2) and (e.ac1 or e.ac2) \
            and f.center > 50
        f.l_pumps_pressurized = l_pumps
        f.r_pumps_pressurized = r_pumps

        # burn allocation per engine half (each engine burns half of the
        # measured total unless single-engine)
        per_engine = []
        n_running = max(1, sum(eng.running))
        for i in range(2):
            per_engine.append(burn / n_running if eng.running[i] else 0.0)

        for i, side in enumerate(("l", "r")):
            need = per_engine[i]
            if need <= 0:
                continue
            other = "r" if side == "l" else "l"
            # center pumps feed first when running
            if c_pumps and f.center > need:
                f.center -= need
                continue
            src = f"inner_{side}"
            # crossfeed lets the other side supply
            if f.xfeed:
                # draw from the fuller side
                if getattr(f, f"inner_{other}") > getattr(f, src):
                    src = f"inner_{other}"
            setattr(f, src, max(0.0, getattr(f, src) - need))

        # outer -> inner auto transfer
        for side in ("l", "r"):
            inner = getattr(f, f"inner_{side}")
            outer = getattr(f, f"outer_{side}")
            if inner < OUTER_XFER_INNER_BELOW_LBS and outer > 0:
                moved = min(outer, OUTER_XFER_RATE_PPS * dt)
                setattr(f, f"outer_{side}", outer - moved)
                setattr(f, f"inner_{side}", inner + moved)

        # feed availability: pumps or gravity (simplified: fuel present)
        f.feed_ok[0] = (f.inner_l + f.center > 10) or \
            (f.xfeed and f.inner_r > 10)
        f.feed_ok[1] = (f.inner_r + f.center > 10) or \
            (f.xfeed and f.inner_l > 10)

        f.total_lbs = f.outer_l + f.inner_l + f.center + f.inner_r + f.outer_r
        self._push_to_fdm()
        # next tick's burn is measured against what we just pushed
        self._last_fdm_total = f.total_lbs
