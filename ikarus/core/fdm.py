"""JSBSim adapter — the only module that touches JSBSim property names.

Everything above this layer works with :class:`FdmState` (plain floats in
aviation units) and the typed setter methods on :class:`JsbsimAdapter`.
All property names used here were verified against the property catalog
of the stock A320 model shipped in the jsbsim 1.3.1 wheel.

Notes on the stock model discovered at M0:
- Only two fuel tanks (left/right wing aggregate).
- ``starter_cmd``/``cutoff_cmd`` exist only as global properties and the
  turbine exposes no EGT, so engine start spool and EGT are modeled in
  Python (see systems/engines.py) and pushed to the FDM via
  ``set-running`` when stabilized.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import jsbsim

from ikarus import config

FPS_TO_KTS = 0.592484
FPS_TO_FPM = 60.0


@dataclass
class EngineFdm:
    n1: float = 0.0            # %
    n2: float = 0.0            # %
    thrust_lbs: float = 0.0
    fuel_flow_pph: float = 0.0
    running: bool = False


@dataclass
class FdmState:
    """Snapshot of the flight dynamics state after the last FDM step."""

    sim_time_s: float = 0.0
    # Position
    lat_deg: float = 0.0
    lon_deg: float = 0.0
    alt_ft: float = 0.0
    agl_ft: float = 0.0
    # Attitude (deg) and body rates (rad/s)
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    hdg_true_deg: float = 0.0
    p_rps: float = 0.0
    q_rps: float = 0.0
    r_rps: float = 0.0
    # Air data
    cas_kts: float = 0.0
    tas_kts: float = 0.0
    mach: float = 0.0
    alpha_deg: float = 0.0
    nz_g: float = 1.0
    # Path
    gs_kts: float = 0.0
    vs_fpm: float = 0.0
    gamma_deg: float = 0.0
    track_true_deg: float = 0.0
    # Ground / config
    wow: bool = True
    gear_pos_norm: float = 1.0
    flap_pos_norm: float = 0.0
    speedbrake_pos_norm: float = 0.0
    # Surfaces / trim (for F/CTL page and law feedback)
    elevator_pos_norm: float = 0.0
    aileron_pos_norm: float = 0.0
    rudder_pos_norm: float = 0.0
    pitch_trim_norm: float = 0.0
    # Mass & fuel
    weight_lbs: float = 0.0
    tank_lbs: list[float] = field(default_factory=list)
    total_fuel_lbs: float = 0.0
    # Propulsion
    engines: list[EngineFdm] = field(default_factory=list)


class JsbsimAdapter:
    """Owns the FGFDMExec instance and translates to/from FdmState."""

    def __init__(self, aircraft: str = config.AIRCRAFT_MODEL,
                 dt: float = 1.0 / config.FDM_HZ,
                 root_dir: str | None = None):
        self._fdm = jsbsim.FGFDMExec(root_dir)
        self._fdm.set_debug_level(0)
        self._fdm.set_dt(dt)
        if not self._fdm.load_model(aircraft):
            raise RuntimeError(f"failed to load JSBSim model {aircraft!r}")
        self.dt = dt
        self.n_engines = config.N_ENGINES
        self.n_tanks = self._count_tanks()
        self.state = FdmState(
            engines=[EngineFdm() for _ in range(self.n_engines)],
            tank_lbs=[0.0] * self.n_tanks,
        )

    def _count_tanks(self) -> int:
        n = 0
        catalog = self._fdm.query_property_catalog("propulsion/tank")
        lines = catalog if isinstance(catalog, list) else catalog.splitlines()
        for line in lines:
            if "/contents-lbs" in line:
                n += 1
        return n

    # --- generic access (used sparingly; prefer the typed helpers) ---------

    def get(self, prop: str) -> float:
        return self._fdm.get_property_value(prop)

    def set(self, prop: str, value: float) -> None:
        self._fdm.set_property_value(prop, value)

    # --- stepping -----------------------------------------------------------

    def step(self) -> None:
        """Advance the FDM one dt and refresh self.state."""
        self._fdm.run()
        self._read_state()

    def _read_state(self) -> None:
        fdm, s = self._fdm, self.state
        s.sim_time_s = fdm.get_property_value("simulation/sim-time-sec")
        s.lat_deg = fdm.get_property_value("position/lat-gc-deg")
        s.lon_deg = fdm.get_property_value("position/long-gc-deg")
        s.alt_ft = fdm.get_property_value("position/h-sl-ft")
        s.agl_ft = fdm.get_property_value("position/h-agl-ft")
        s.pitch_deg = fdm.get_property_value("attitude/theta-deg")
        s.roll_deg = fdm.get_property_value("attitude/phi-deg")
        s.hdg_true_deg = fdm.get_property_value("attitude/psi-deg") % 360.0
        s.p_rps = fdm.get_property_value("velocities/p-rad_sec")
        s.q_rps = fdm.get_property_value("velocities/q-rad_sec")
        s.r_rps = fdm.get_property_value("velocities/r-rad_sec")
        s.cas_kts = fdm.get_property_value("velocities/vc-kts")
        s.tas_kts = fdm.get_property_value("velocities/vtrue-kts")
        s.mach = fdm.get_property_value("velocities/mach")
        s.alpha_deg = fdm.get_property_value("aero/alpha-deg")
        s.nz_g = fdm.get_property_value("accelerations/Nz")
        s.gs_kts = fdm.get_property_value("velocities/vg-fps") * FPS_TO_KTS
        s.vs_fpm = fdm.get_property_value("velocities/h-dot-fps") * FPS_TO_FPM
        s.gamma_deg = fdm.get_property_value("flight-path/gamma-deg")
        s.track_true_deg = math.degrees(
            fdm.get_property_value("flight-path/psi-gt-rad")) % 360.0
        s.wow = fdm.get_property_value("gear/wow") != 0.0
        s.gear_pos_norm = fdm.get_property_value("gear/gear-pos-norm")
        s.flap_pos_norm = fdm.get_property_value("fcs/flap-pos-norm")
        s.speedbrake_pos_norm = fdm.get_property_value("fcs/speedbrake-pos-norm")
        s.elevator_pos_norm = fdm.get_property_value("fcs/elevator-pos-norm")
        s.aileron_pos_norm = fdm.get_property_value("fcs/left-aileron-pos-norm")
        s.rudder_pos_norm = fdm.get_property_value("fcs/rudder-pos-norm")
        s.pitch_trim_norm = fdm.get_property_value("fcs/pitch-trim-cmd-norm")
        s.weight_lbs = fdm.get_property_value("inertia/weight-lbs")
        s.total_fuel_lbs = fdm.get_property_value("propulsion/total-fuel-lbs")
        for i in range(self.n_tanks):
            s.tank_lbs[i] = fdm.get_property_value(
                f"propulsion/tank[{i}]/contents-lbs")
        for i, eng in enumerate(s.engines):
            pre = f"propulsion/engine[{i}]"
            eng.n1 = fdm.get_property_value(f"{pre}/n1")
            eng.n2 = fdm.get_property_value(f"{pre}/n2")
            eng.thrust_lbs = fdm.get_property_value(f"{pre}/thrust-lbs")
            eng.fuel_flow_pph = fdm.get_property_value(
                f"{pre}/fuel-flow-rate-pps") * 3600.0
            eng.running = fdm.get_property_value(f"{pre}/set-running") != 0.0

    # --- control writes -----------------------------------------------------

    def set_elevator(self, cmd_norm: float) -> None:
        self._fdm.set_property_value("fcs/elevator-cmd-norm", cmd_norm)

    def set_aileron(self, cmd_norm: float) -> None:
        self._fdm.set_property_value("fcs/aileron-cmd-norm", cmd_norm)

    def set_rudder(self, cmd_norm: float) -> None:
        self._fdm.set_property_value("fcs/rudder-cmd-norm", cmd_norm)

    def set_pitch_trim(self, cmd_norm: float) -> None:
        self._fdm.set_property_value("fcs/pitch-trim-cmd-norm", cmd_norm)

    def set_throttle(self, engine: int, cmd_norm: float) -> None:
        suffix = "" if engine == 0 else f"[{engine}]"
        self._fdm.set_property_value(f"fcs/throttle-cmd-norm{suffix}", cmd_norm)

    def set_flaps(self, cmd_norm: float) -> None:
        self._fdm.set_property_value("fcs/flap-cmd-norm", cmd_norm)

    def set_gear(self, down: bool) -> None:
        self._fdm.set_property_value("gear/gear-cmd-norm", 1.0 if down else 0.0)

    def set_speedbrake(self, cmd_norm: float) -> None:
        self._fdm.set_property_value("fcs/speedbrake-cmd-norm", cmd_norm)

    def set_brakes(self, cmd_norm: float) -> None:
        self._fdm.set_property_value("fcs/left-brake-cmd-norm", cmd_norm)
        self._fdm.set_property_value("fcs/right-brake-cmd-norm", cmd_norm)

    def set_engine_running(self, engine: int, running: bool) -> None:
        if running:
            # propulsion-level InitRunning: spools the turbine to idle
            # (the per-engine set-running property only sets a flag)
            self._fdm.set_property_value("propulsion/set-running",
                                         float(engine))
        else:
            self._fdm.set_property_value(
                f"propulsion/engine[{engine}]/set-running", 0.0)

    def set_tank_lbs(self, tank: int, lbs: float) -> None:
        self._fdm.set_property_value(
            f"propulsion/tank[{tank}]/contents-lbs", max(0.0, lbs))

    def set_wind_ned_fps(self, north: float, east: float, down: float) -> None:
        self._fdm.set_property_value("atmosphere/wind-north-fps", north)
        self._fdm.set_property_value("atmosphere/wind-east-fps", east)
        self._fdm.set_property_value("atmosphere/wind-down-fps", down)

    # --- initial conditions ---------------------------------------------------

    def init_cruise(self, lat_deg: float = config.DEFAULT_LAT_DEG,
                    lon_deg: float = config.DEFAULT_LON_DEG,
                    alt_ft: float = config.CRUISE_ALT_FT,
                    cas_kts: float = config.CRUISE_CAS_KTS,
                    hdg_deg: float = 90.0) -> None:
        """In-flight start: level cruise, engines running, trimmed."""
        fdm = self._fdm
        fdm.set_property_value("ic/lat-gc-deg", lat_deg)
        fdm.set_property_value("ic/long-gc-deg", lon_deg)
        fdm.set_property_value("ic/h-sl-ft", alt_ft)
        fdm.set_property_value("ic/vc-kts", cas_kts)
        fdm.set_property_value("ic/psi-true-deg", hdg_deg)
        fdm.set_property_value("ic/gamma-deg", 0.0)
        fdm.run_ic()
        fdm.set_property_value("propulsion/set-running", -1)  # -1 = all engines
        self.set_gear(False)
        self.set_flaps(0.0)
        for i in range(self.n_engines):
            self.set_throttle(i, 0.6)
        self._trim()
        self._read_state()

    def init_runway(self, lat_deg: float = config.DEFAULT_LAT_DEG,
                    lon_deg: float = config.DEFAULT_LON_DEG,
                    hdg_deg: float = 70.0,
                    engines_running: bool = True) -> None:
        """On-ground start, lined up, engines at idle (or cold)."""
        fdm = self._fdm
        fdm.set_property_value("ic/lat-gc-deg", lat_deg)
        fdm.set_property_value("ic/long-gc-deg", lon_deg)
        fdm.set_property_value("ic/psi-true-deg", hdg_deg)
        fdm.set_property_value("ic/h-agl-ft", 5.0)
        fdm.set_property_value("ic/vc-kts", 0.0)
        fdm.set_property_value("gear/gear-cmd-norm", 1.0)
        fdm.run_ic()
        if engines_running:
            fdm.set_property_value("propulsion/set-running", -1)
        for i in range(self.n_engines):
            self.set_throttle(i, 0.0)
        self._read_state()

    def _trim(self) -> None:
        # Try full trim (includes throttle) first, then longitudinal only.
        # Trim failure is survivable: the FBW/AP loops close on measured
        # state and will settle the aircraft themselves.
        for mode in (1, 0):
            try:
                self._fdm.do_trim(mode)
                return
            except (RuntimeError, jsbsim.TrimFailureError):
                continue
