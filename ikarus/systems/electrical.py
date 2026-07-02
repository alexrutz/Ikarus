"""Electrical system: sources, buses, contactor logic.

Modeling level: boolean bus power decided by an ordered source-priority
list per bus each tick (that IS the A320 contactor logic to a good
approximation), battery charge as an integrator. No volts/amps network.

Sources: GEN1, GEN2, APU GEN, EXT PWR, BAT1/2 (+ TRs implicit: DC buses
follow their AC side unless on batteries alone).
"""

from __future__ import annotations

from ikarus.systems.base import System

GEN_MIN_N2_PCT = 55.0        # engine generator online threshold
APU_GEN_MIN_N = 95.0
BAT_DISCHARGE_PER_S = 1.0 / (25 * 60)   # ~25 min of batteries
BAT_CHARGE_PER_S = 1.0 / (45 * 60)


class ElectricalSystem(System):
    name = "electrical"

    def init_situation(self, situation: str) -> None:
        e = self.state.elec
        if situation == "cold_dark":
            e.bat1 = e.bat2 = False
            e.ext_pwr = False
            e.ext_pwr_avail = True
        else:
            e.bat1 = e.bat2 = True
            e.ext_pwr = False
            e.ext_pwr_avail = self.state.fdm.wow

    def update(self, dt: float) -> None:
        e, eng, apu, fdm = (self.state.elec, self.state.eng,
                            self.state.apu, self.state.fdm)

        gen1_on = (e.gen1 and not e.gen1_fault and eng.running[0]
                   and eng.n2[0] > GEN_MIN_N2_PCT)
        gen2_on = (e.gen2 and not e.gen2_fault and eng.running[1]
                   and eng.n2[1] > GEN_MIN_N2_PCT)
        apu_gen_on = e.apu_gen and apu.avail and apu.n_pct > APU_GEN_MIN_N
        ext_on = e.ext_pwr and e.ext_pwr_avail and fdm.wow
        bat_on = (e.bat1 and e.bat1_charge > 0.05) \
            or (e.bat2 and e.bat2_charge > 0.05)

        # AC bus source priority (own gen > ext > apu > cross-tie)
        def pick(own_gen: bool, own_name: str, other_ac: bool) -> str:
            if own_gen:
                return own_name
            if ext_on:
                return "EXT"
            if apu_gen_on:
                return "APU"
            if e.bus_tie and other_ac:
                return "XTIE"
            return ""

        # two-pass so cross-tie sees the other side's final state
        ac1_src = pick(gen1_on, "GEN1", gen2_on or ext_on or apu_gen_on)
        ac2_src = pick(gen2_on, "GEN2", gen1_on or ext_on or apu_gen_on)
        e.ac1_source, e.ac2_source = ac1_src, ac2_src
        e.ac1, e.ac2 = bool(ac1_src), bool(ac2_src)

        # AC ESS: AC1, else AC2 (auto transfer)
        e.ac_ess = e.ac1 or e.ac2
        # DC buses follow their TRs; DC BAT from DC1/2; ESS falls to BAT
        e.dc1 = e.ac1 or e.ac2
        e.dc2 = e.ac2 or e.ac1
        e.dc_bat = e.dc1 or e.dc2 or bat_on
        e.dc_ess = e.dc1 or e.dc2 or bat_on
        e.hot1 = e.bat1_charge > 0.02
        e.hot2 = e.bat2_charge > 0.02

        # battery charge/discharge
        any_ac = e.ac1 or e.ac2
        for i in (1, 2):
            charge = getattr(e, f"bat{i}_charge")
            sw = getattr(e, f"bat{i}")
            if any_ac and sw:
                charge = min(1.0, charge + BAT_CHARGE_PER_S * dt)
            elif sw and not any_ac and (e.dc_bat or e.dc_ess):
                charge = max(0.0, charge - BAT_DISCHARGE_PER_S * dt)
            setattr(e, f"bat{i}_charge", charge)
            setattr(e, f"bat{i}_voltage",
                    round(22.0 + 6.0 * charge, 1) if charge > 0.02 else 0.0)

        e.gen1_load_pct = 30.0 if ac1_src == "GEN1" else 0.0
        e.gen2_load_pct = 30.0 if ac2_src == "GEN2" else 0.0
        if ac1_src == "GEN1" and ac2_src in ("XTIE",):
            e.gen1_load_pct = 55.0
        if ac2_src == "GEN2" and ac1_src in ("XTIE",):
            e.gen2_load_pct = 55.0
        apu.gen_load_pct = 40.0 if "APU" in (ac1_src, ac2_src) else 0.0
