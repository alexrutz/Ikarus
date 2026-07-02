"""Engines: master/mode switches and the start/shutdown sequencer.

The stock A320 turbine model exposes no usable per-engine starter
dynamics (M0 finding), so the start spool (N2/N1/EGT/FF) is modeled
here and `set-running` flips the JSBSim engine once stabilized at idle.
When running, displayed values come from JSBSim.

Start sequence (IGN/START mode + master ON, needs duct pressure):
starter -> N2 rises -> ignition/fuel at 22% N2 -> lightoff EGT rise ->
starter cutout at 50% -> accelerate to idle -> RUNNING.
"""

from __future__ import annotations

from ikarus.systems.base import System

IDLE_N1 = 19.5
IDLE_N2 = 58.0
IDLE_EGT_C = 390.0
IDLE_FF_PPH = 600.0
START_DUCT_MIN_PSI = 20.0
FUEL_ON_N2 = 22.0
STARTER_CUTOUT_N2 = 50.0
CRANK_N2_PER_S = 2.2
ACCEL_N2_PER_S = 3.6
SPOOLDOWN_N2_PER_S = 4.0
EGT_TAU_S = 3.0
LIGHTOFF_EGT_C = 550.0


class EngineSystem(System):
    name = "engines"

    def init_situation(self, situation: str) -> None:
        eng = self.state.eng
        running = situation in ("cruise", "runway")
        for i in range(2):
            eng.master[i] = running
            eng.phase[i] = "RUNNING" if running else "OFF"
            eng.running[i] = running
            if running:
                eng.n1[i], eng.n2[i] = IDLE_N1, IDLE_N2
                eng.egt_c[i] = IDLE_EGT_C
        eng.mode = "NORM"

    def update(self, dt: float) -> None:
        eng, bleed, fuel = self.state.eng, self.state.bleed, self.state.fuel
        fdm_engines = self.state.fdm.engines

        for i in range(2):
            phase = eng.phase[i]
            duct = bleed.duct1_psi if i == 0 else bleed.duct2_psi
            feed = fuel.feed_ok[i]

            if phase in ("OFF", "SHUTDOWN"):
                self._spool_down(eng, i, dt)
                if eng.n2[i] < 1.0:
                    eng.phase[i] = "OFF"
                if (eng.mode == "IGN_START" and eng.master[i]
                        and duct > START_DUCT_MIN_PSI and feed):
                    eng.phase[i] = "CRANK"
            elif phase == "CRANK":
                eng.n2[i] = min(eng.n2[i] + CRANK_N2_PER_S * dt,
                                STARTER_CUTOUT_N2 + 2)
                self._egt_toward(eng, i, 80.0, dt)
                if not eng.master[i] or duct < START_DUCT_MIN_PSI / 2:
                    eng.phase[i] = "SHUTDOWN"
                elif eng.n2[i] >= FUEL_ON_N2 and feed:
                    eng.phase[i] = "IGNITION"
            elif phase == "IGNITION":
                eng.n2[i] += CRANK_N2_PER_S * dt
                eng.ff_pph[i] = 300.0
                self._egt_toward(eng, i, LIGHTOFF_EGT_C, dt)
                if not eng.master[i]:
                    eng.phase[i] = "SHUTDOWN"
                elif eng.n2[i] >= STARTER_CUTOUT_N2:
                    eng.phase[i] = "ACCEL"
            elif phase == "ACCEL":
                eng.n2[i] += ACCEL_N2_PER_S * dt
                eng.ff_pph[i] = 450.0
                self._egt_toward(eng, i, LIGHTOFF_EGT_C + 60, dt)
                if not eng.master[i]:
                    eng.phase[i] = "SHUTDOWN"
                elif eng.n2[i] >= IDLE_N2:
                    eng.phase[i] = "RUNNING"
                    eng.running[i] = True
                    self.adapter.set_engine_running(i, True)
            elif phase == "RUNNING":
                # displayed values from the FDM
                eng.n1[i] = fdm_engines[i].n1
                eng.n2[i] = fdm_engines[i].n2
                eng.ff_pph[i] = fdm_engines[i].fuel_flow_pph
                self._egt_toward(
                    eng, i, IDLE_EGT_C + (eng.n1[i] - IDLE_N1) * 4.5, dt)
                if not eng.master[i] or not feed:
                    eng.phase[i] = "SHUTDOWN"
                    eng.running[i] = False
                    self.adapter.set_engine_running(i, False)

            if phase != "RUNNING":
                eng.n1[i] = max(0.0, eng.n2[i] - 38.0) * (IDLE_N1 / 20.0)

    def _spool_down(self, eng, i: int, dt: float) -> None:
        eng.n2[i] = max(0.0, eng.n2[i] - SPOOLDOWN_N2_PER_S * dt)
        eng.ff_pph[i] = 0.0
        self._egt_toward(eng, i, 15.0, dt, tau=20.0)

    @staticmethod
    def _egt_toward(eng, i: int, target: float, dt: float,
                    tau: float = EGT_TAU_S) -> None:
        eng.egt_c[i] += (target - eng.egt_c[i]) * min(1.0, dt / tau)
