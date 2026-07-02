"""Hydraulics: Green (ENG1 pump), Blue (elec pump), Yellow (ENG2 + elec).

First-order pressure response toward 3000 psi when a pump delivers,
decay otherwise. PTU transfers G<->Y on differential pressure. RAT
pressurizes Blue when deployed (M5).
"""

from __future__ import annotations

from ikarus.systems.base import System

NOMINAL_PSI = 3000.0
LO_PR_PSI = 1450.0
PRESSURE_TAU_S = 2.5
DECAY_TAU_S = 6.0
PTU_DELTA_ON_PSI = 500.0
PTU_DELTA_OFF_PSI = 150.0
PUMP_MIN_N2 = 15.0           # engine-driven pump effective during start too


class HydraulicSystem(System):
    name = "hydraulics"

    def init_situation(self, situation: str) -> None:
        h = self.state.hyd
        if situation == "cold_dark":
            h.green_press_psi = h.blue_press_psi = h.yellow_press_psi = 0.0
            h.blue_elec_pump = True   # AUTO: runs when AC powered + eng on
        else:
            h.green_press_psi = h.blue_press_psi = h.yellow_press_psi = NOMINAL_PSI

    def update(self, dt: float) -> None:
        h, e, eng, fdm = (self.state.hyd, self.state.elec,
                          self.state.eng, self.state.fdm)

        g_pump = (h.eng1_pump and eng.n2[0] > PUMP_MIN_N2
                  and h.green_qty > 0.2)
        y_eng_pump = (h.eng2_pump and eng.n2[1] > PUMP_MIN_N2
                      and h.yellow_qty > 0.2)
        y_elec = h.yellow_elec_pump and e.ac2 and h.yellow_qty > 0.2
        # blue elec pump: AUTO = runs when any engine running (or in flight)
        blue_auto_run = any(eng.running) or not fdm.wow
        b_pump = (h.blue_elec_pump and e.ac1 and blue_auto_run
                  and h.blue_qty > 0.2) or h.rat_deployed

        def relax(current: float, powered: bool) -> float:
            target = NOMINAL_PSI if powered else 0.0
            tau = PRESSURE_TAU_S if powered else DECAY_TAU_S
            return current + (target - current) * min(1.0, dt / tau)

        green_powered = g_pump
        yellow_powered = y_eng_pump or y_elec

        # PTU: bidirectional on pressure differential (with hysteresis so
        # it doesn't cycle), inhibited on the ground during the first
        # engine start (simplified: park brake + one engine only)
        inhibited = (not h.ptu_auto
                     or (fdm.wow and self.state.ctl.parking_brake
                         and sum(eng.running) == 1))
        diff = h.green_press_psi - h.yellow_press_psi
        if inhibited or not (green_powered or yellow_powered):
            h.ptu_running = False
        elif abs(diff) > PTU_DELTA_ON_PSI:
            h.ptu_running = True
        elif abs(diff) < PTU_DELTA_OFF_PSI:
            h.ptu_running = False
        # in between: latch the previous state
        if h.ptu_running:
            if green_powered and not yellow_powered:
                yellow_powered = h.yellow_qty > 0.2
            elif yellow_powered and not green_powered:
                green_powered = h.green_qty > 0.2

        h.green_press_psi = relax(h.green_press_psi, green_powered)
        h.blue_press_psi = relax(h.blue_press_psi, b_pump)
        h.yellow_press_psi = relax(h.yellow_press_psi, yellow_powered)

        # surface availability for F/CTL
        fctl = self.state.fctl
        g_ok = h.green_press_psi > LO_PR_PSI
        b_ok = h.blue_press_psi > LO_PR_PSI
        y_ok = h.yellow_press_psi > LO_PR_PSI
        fctl.ail_avail = g_ok or b_ok
        fctl.elev_avail = g_ok or b_ok or y_ok
        fctl.rud_avail = g_ok or b_ok or y_ok
        fctl.spoilers_avail = g_ok or y_ok
