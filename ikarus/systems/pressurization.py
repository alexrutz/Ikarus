"""Pressurization: cabin-altitude integrator with an auto schedule."""

from __future__ import annotations

from ikarus.systems.base import System

MAX_DELTA_P_PSI = 8.6
CABIN_RATE_LIMIT_FPM = 750.0
UNPRESSURIZED_TAU_S = 60.0       # cabin drifts to outside alt w/o packs
FT_PER_PSI = 2200.0              # rough pressure-to-altitude slope


class PressurizationSystem(System):
    name = "pressurization"

    def init_situation(self, situation: str) -> None:
        p, fdm = self.state.press, self.state.fdm
        if situation == "cruise":
            p.cabin_alt_ft = 6000.0
        else:
            p.cabin_alt_ft = max(0.0, fdm.alt_ft)
        p.cabin_vs_fpm = 0.0

    def update(self, dt: float) -> None:
        p, b, fdm = self.state.press, self.state.bleed, self.state.fdm

        packs_on = b.pack1_flow or b.pack2_flow
        if packs_on:
            # auto schedule: cabin climbs to ~8000 at FL390, proportional
            target = max(self.state.press.ldg_elev_ft if fdm.alt_ft < 8000
                         else 0.0, fdm.alt_ft * 8000.0 / 39000.0)
            target = min(target, fdm.alt_ft)
        else:
            target = fdm.alt_ft  # leaks toward outside altitude

        err = target - p.cabin_alt_ft
        rate_limit = CABIN_RATE_LIMIT_FPM if packs_on else 2500.0
        tau = 25.0 if packs_on else UNPRESSURIZED_TAU_S
        vs = max(-rate_limit, min(rate_limit, err / tau * 60.0))
        p.cabin_alt_ft += vs / 60.0 * dt
        p.cabin_vs_fpm = round(vs / 10) * 10

        p.delta_p_psi = max(0.0, min(
            MAX_DELTA_P_PSI, (fdm.alt_ft - p.cabin_alt_ft) / FT_PER_PSI))
        # outflow valve: closes as demand for pressure rises
        p.outflow_pos = max(0.0, min(1.0, 1.0 - p.delta_p_psi / MAX_DELTA_P_PSI))
