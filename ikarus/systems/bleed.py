"""Bleed air: engine/APU sources, crossbleed, ducts, packs."""

from __future__ import annotations

from ikarus.systems.base import System

ENG_BLEED_PSI = 36.0
APU_BLEED_PSI = 40.0
DUCT_TAU_S = 2.0
ENG_BLEED_MIN_N2 = 50.0


class BleedSystem(System):
    name = "bleed"

    def init_situation(self, situation: str) -> None:
        b = self.state.bleed
        if situation == "cold_dark":
            b.apu_bleed = False
            b.duct1_psi = b.duct2_psi = 0.0

    def update(self, dt: float) -> None:
        b, eng, apu = self.state.bleed, self.state.eng, self.state.apu

        b.eng1_bleed_avail = eng.running[0] and eng.n2[0] > ENG_BLEED_MIN_N2
        b.eng2_bleed_avail = eng.running[1] and eng.n2[1] > ENG_BLEED_MIN_N2
        src1 = ENG_BLEED_PSI if (b.eng1_bleed and b.eng1_bleed_avail) else 0.0
        src2 = ENG_BLEED_PSI if (b.eng2_bleed and b.eng2_bleed_avail) else 0.0
        apu_psi = APU_BLEED_PSI if (b.apu_bleed and apu.avail) else 0.0
        # APU bleed feeds duct 1 directly
        src1 = max(src1, apu_psi)

        # crossbleed: AUTO opens when APU bleed is supplying, else per switch
        if b.xbleed == "OPEN":
            b.xbleed_open = True
        elif b.xbleed == "SHUT":
            b.xbleed_open = False
        else:
            b.xbleed_open = apu_psi > 0
        if b.xbleed_open:
            src1 = src2 = max(src1, src2)

        b.duct1_psi += (src1 - b.duct1_psi) * min(1.0, dt / DUCT_TAU_S)
        b.duct2_psi += (src2 - b.duct2_psi) * min(1.0, dt / DUCT_TAU_S)

        b.pack1_flow = b.pack1 and b.duct1_psi > 10.0
        b.pack2_flow = b.pack2 and b.duct2_psi > 10.0
