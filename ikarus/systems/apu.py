"""APU: start state machine with N/EGT spool, supplies GEN + bleed."""

from __future__ import annotations

from ikarus.systems.base import System

START_SPOOL_PCT_PER_S = 3.3      # ~30 s to 100%
SHUTDOWN_PCT_PER_S = 5.0
EGT_START_PEAK_C = 720.0
EGT_RUN_C = 390.0
EGT_TAU_S = 4.0


class ApuSystem(System):
    name = "apu"

    def init_situation(self, situation: str) -> None:
        a = self.state.apu
        if situation == "cold_dark":
            a.master = False
            a.state = "OFF"
            a.n_pct = 0.0
            a.avail = False
        # in-air/runway starts leave the APU off but available to start

    def update(self, dt: float) -> None:
        a, e, f = self.state.apu, self.state.elec, self.state.fuel

        powered = e.dc_bat or e.dc_ess     # needs battery/DC power
        fuel_ok = f.total_lbs > 100

        if a.state == "OFF":
            a.flap_open = False
            if a.master and powered:
                a.flap_open = True
                if a.start_pb and fuel_ok:
                    a.state = "START"
        elif a.state == "START":
            if not a.master or not powered:
                a.state = "COOLDOWN"
            else:
                a.n_pct = min(100.0, a.n_pct + START_SPOOL_PCT_PER_S * dt)
                if a.n_pct >= 99.5:
                    a.state = "AVAIL"
                    a.start_pb = False
        elif a.state == "AVAIL":
            a.n_pct = 100.0
            if not a.master or not fuel_ok:
                a.state = "COOLDOWN"
        elif a.state == "COOLDOWN":
            a.n_pct = max(0.0, a.n_pct - SHUTDOWN_PCT_PER_S * dt)
            if a.n_pct <= 0.5:
                a.state = "OFF"
                a.n_pct = 0.0

        a.avail = a.state == "AVAIL"

        # EGT: peak during start, settle when running, ambient when off
        if a.state == "START":
            target = EGT_START_PEAK_C * min(1.0, a.n_pct / 60.0)
        elif a.state == "AVAIL":
            target = EGT_RUN_C + a.gen_load_pct
        else:
            target = 15.0 + 380.0 * (a.n_pct / 100.0)
        a.egt_c += (target - a.egt_c) * min(1.0, dt / EGT_TAU_S)
