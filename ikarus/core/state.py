"""SimState: the central state tree.

Every section is a plain dataclass owned by exactly one system (the
single-writer rule); any system may read any section. The WebSocket
snapshot is serialized from this same tree — there is no second data
model between simulation and displays.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ikarus.core.fdm import FdmState


@dataclass
class ControlsState:
    """Pilot inceptor state (keyboard/mouse fallback controls)."""

    pitch_input: float = 0.0     # -1..1, nose-up positive, decays to 0
    roll_input: float = 0.0      # -1..1, right positive, decays to 0
    rudder_input: float = 0.0    # -1..1, right positive, decays to 0
    # Sidestick attitude targets (used when AP is off)
    pitch_target_deg: float = 0.0
    roll_target_deg: float = 0.0
    # Thrust levers: a detent plus a manual position used in MAN
    thrust_detent: str = "IDLE"  # IDLE | MAN | CLB | FLX | TOGA
    thrust_manual: float = 0.0   # 0..1, lever position within manual range
    flaps_setting: int = 0       # 0..4 = A320 flap lever positions
    gear_down: bool = True
    speedbrake: float = 0.0      # 0..1
    parking_brake: bool = True


@dataclass
class FcuState:
    """Flight Control Unit: windows, selected/managed, engagement switches."""

    spd_kts: float = 280.0
    spd_is_mach: bool = False
    spd_managed: bool = False    # managed speed arrives with the FMS (M3)
    hdg_deg: float = 90.0
    hdg_managed: bool = False    # dashes; NAV mode arrives with M3
    alt_ft: float = 33000.0
    vs_fpm: float | None = None  # None = window dashed
    ap1: bool = False
    fd: bool = True
    athr: bool = False           # armed/active master switch
    loc: bool = False            # LOC button latched
    appr: bool = False           # APPR button latched (arms LOC + G/S)


@dataclass
class FmaState:
    """Flight Mode Annunciator: five columns, rendered by the PFD."""

    thrust: str = ""             # col 1 (green or white if MAN)
    thrust_man: bool = False     # white MAN annunciation style
    vertical: str = ""           # col 2 active (green)
    vertical_armed: str = ""     # col 2 armed (cyan)
    lateral: str = ""            # col 3 active (green)
    lateral_armed: str = ""      # col 3 armed (cyan)
    ap: str = ""                 # col 5 line 1: AP1 / ""
    fd: str = ""                 # col 5 line 2: 1FD- style, simplified "FD"
    athr: str = ""               # col 5 line 3: A/THR (white=active, cyan=armed)
    athr_active: bool = False


@dataclass
class GuidanceState:
    """Autoflight guidance output: targets the FBW inner loop flies.

    Written only by the autoflight system. FD bars display the same
    targets, so the flight director is this state rendered.
    """

    pitch_target_deg: float = 0.0
    roll_target_deg: float = 0.0
    target_cas_kts: float = 280.0   # resolved (mach converted) A/THR target
    law: str = "normal"             # normal | alternate | direct (M5)


@dataclass
class RadioState:
    """Nav receivers (written by RadioSystem; frequencies set by commands)."""

    nav1_freq_khz: float = 0.0
    nav2_freq_khz: float = 0.0
    nav1_ident: str = ""
    nav1_bearing_mag: float = 0.0
    nav1_dme_nm: float = 0.0
    nav1_ok: bool = False
    nav2_ident: str = ""
    nav2_bearing_mag: float = 0.0
    nav2_dme_nm: float = 0.0
    nav2_ok: bool = False
    # ILS (auto-tuned from the selected approach)
    ils_ok: bool = False
    ils_ident: str = ""
    ils_course_mag: float = 0.0
    ils_loc_dots: float = 0.0    # + = fly right
    ils_gs_dots: float = 0.0     # + = fly up (below path)
    ils_dme_nm: float = 0.0


@dataclass
class FmsLegState:
    """One flight-plan leg as exposed to guidance and displays."""

    ident: str
    lat: float
    lon: float
    alt_above: float | None = None
    alt_below: float | None = None
    speed: float | None = None


@dataclass
class FmsState:
    """Flight plan + lateral/vertical guidance data (written by FmsSystem)."""

    origin: str = ""
    dest: str = ""
    dep_runway: str = ""
    arr_runway: str = ""
    sid: str = ""
    star: str = ""
    approach: str = ""
    legs: list[FmsLegState] = field(default_factory=list)
    active_idx: int = -1
    plan_version: int = 0        # bumped on every plan change
    # lateral guidance for NAV mode
    xtk_nm: float = 0.0
    course_mag: float = 0.0      # active leg course
    dtg_nm: float = 0.0          # distance to active waypoint
    nav_roll_cmd_deg: float = 0.0
    nav_ok: bool = False
    # vertical
    dist_to_dest_nm: float = 0.0
    tod_dist_nm: float = -1.0    # along-track distance to top-of-descent
    managed_spd_kts: float = 280.0
    vdev_ft: float = 0.0         # deviation from descent profile (+= high)
    clb_constraint_ft: float | None = None  # lowest upcoming at-or-below
    # approach geometry for the ILS receiver (from the selected approach)
    appr_thr_lat: float = 0.0
    appr_thr_lon: float = 0.0
    appr_thr_elev_ft: float = 0.0
    appr_course_mag: float = 0.0
    appr_gs_deg: float = 3.0
    appr_freq_khz: float = 0.0
    appr_ident: str = ""
    # MCDU display: 14 lines of segment lists [(text, color), ...]
    mcdu_lines: list = field(default_factory=list)
    mcdu_scratch: str = ""
    mcdu_page: str = "INIT"


@dataclass
class ElecState:
    """Electrical system (written by ElectricalSystem)."""

    # switches (set by commands)
    bat1: bool = False
    bat2: bool = False
    gen1: bool = True            # engine generator pushbuttons
    gen2: bool = True
    ext_pwr: bool = False        # EXT PWR pushbutton (in use)
    apu_gen: bool = True
    bus_tie: bool = True
    # availability
    ext_pwr_avail: bool = True   # ground power connected (on ground)
    # bus power states
    ac1: bool = False
    ac2: bool = False
    ac_ess: bool = False
    dc1: bool = False
    dc2: bool = False
    dc_bat: bool = False
    dc_ess: bool = False
    hot1: bool = True
    hot2: bool = True
    # sources feeding AC1/AC2 ("GEN1", "EXT", "APU", "XTIE", "")
    ac1_source: str = ""
    ac2_source: str = ""
    bat1_voltage: float = 25.8
    bat2_voltage: float = 25.8
    bat1_charge: float = 1.0     # 0..1
    bat2_charge: float = 1.0
    gen1_load_pct: float = 0.0
    gen2_load_pct: float = 0.0
    gen1_fault: bool = False
    gen2_fault: bool = False


@dataclass
class HydState:
    """Hydraulics G/B/Y (written by HydraulicSystem)."""

    green_press_psi: float = 0.0
    blue_press_psi: float = 0.0
    yellow_press_psi: float = 0.0
    green_qty: float = 1.0       # normalized reservoir quantity
    blue_qty: float = 1.0
    yellow_qty: float = 1.0
    # pump switches
    eng1_pump: bool = True       # green
    eng2_pump: bool = True       # yellow
    blue_elec_pump: bool = True  # AUTO
    yellow_elec_pump: bool = False
    ptu_auto: bool = True
    ptu_running: bool = False
    rat_deployed: bool = False


@dataclass
class FuelState:
    """Fuel system: 5 logical tanks mapped onto the FDM's 2 (written by
    FuelSystem)."""

    # lbs per logical tank
    outer_l: float = 1500.0
    inner_l: float = 12000.0
    center: float = 0.0
    inner_r: float = 12000.0
    outer_r: float = 1500.0
    # pump switches
    pump_l1: bool = True
    pump_l2: bool = True
    pump_c1: bool = False
    pump_c2: bool = False
    pump_r1: bool = True
    pump_r2: bool = True
    xfeed: bool = False
    # computed
    feed_ok: list[bool] = field(default_factory=lambda: [True, True])
    l_pumps_pressurized: bool = False
    r_pumps_pressurized: bool = False
    total_lbs: float = 27000.0


@dataclass
class BleedState:
    """Bleed air / pneumatics (written by BleedSystem)."""

    eng1_bleed: bool = True      # switches
    eng2_bleed: bool = True
    apu_bleed: bool = False
    xbleed: str = "AUTO"         # AUTO | OPEN | SHUT
    pack1: bool = True
    pack2: bool = True
    # computed
    duct1_psi: float = 0.0
    duct2_psi: float = 0.0
    xbleed_open: bool = False
    pack1_flow: bool = False
    pack2_flow: bool = False
    eng1_bleed_avail: bool = False
    eng2_bleed_avail: bool = False


@dataclass
class PressState:
    """Pressurization (written by PressurizationSystem)."""

    cabin_alt_ft: float = 0.0
    cabin_vs_fpm: float = 0.0
    delta_p_psi: float = 0.0
    outflow_pos: float = 0.5     # 0 = closed, 1 = full open
    ldg_elev_ft: float = 0.0


@dataclass
class ApuState:
    """APU (written by ApuSystem)."""

    master: bool = False
    start_pb: bool = False
    n_pct: float = 0.0
    egt_c: float = 15.0
    avail: bool = False
    state: str = "OFF"           # OFF | START | AVAIL | COOLDOWN
    flap_open: bool = False
    gen_load_pct: float = 0.0


@dataclass
class EngState:
    """Engine controls + start sequencing (written by EngineSystem).

    N1/N2/EGT/FF as *displayed* — from JSBSim when running, from the
    Python start model while starting (stock model has no per-engine
    starter dynamics).
    """

    master: list[bool] = field(default_factory=lambda: [False, False])
    mode: str = "NORM"           # NORM | IGN_START | CRANK
    phase: list[str] = field(default_factory=lambda: ["OFF", "OFF"])
    # OFF | CRANK | IGNITION | ACCEL | RUNNING | SHUTDOWN | FAIL
    n1: list[float] = field(default_factory=lambda: [0.0, 0.0])
    n2: list[float] = field(default_factory=lambda: [0.0, 0.0])
    egt_c: list[float] = field(default_factory=lambda: [15.0, 15.0])
    ff_pph: list[float] = field(default_factory=lambda: [0.0, 0.0])
    running: list[bool] = field(default_factory=lambda: [False, False])
    fire: list[bool] = field(default_factory=lambda: [False, False])


@dataclass
class FctlState:
    """Flight-control computers & law (written by FlightControlSystem)."""

    elac: list[bool] = field(default_factory=lambda: [True, True])
    sec: list[bool] = field(default_factory=lambda: [True, True, True])
    fac: list[bool] = field(default_factory=lambda: [True, True])
    law: str = "normal"          # normal | alternate | direct
    # surface availability (from hydraulics)
    ail_avail: bool = True
    elev_avail: bool = True
    rud_avail: bool = True
    spoilers_avail: bool = True


@dataclass
class EcamAlert:
    """One active alert line set for the E/WD."""

    id: str
    level: int                   # 3 = warning (red), 2 = caution (amber)
    lines: list = field(default_factory=list)  # [(text, color), ...]
    sd_page: str = ""


@dataclass
class EcamState:
    """ECAM/FWC output (written by FwcSystem)."""

    master_warning: bool = False
    master_caution: bool = False
    flight_phase: int = 1
    alerts: list = field(default_factory=list)      # active EcamAlert list
    memos: list = field(default_factory=list)       # [(text, color), ...]
    sd_page: str = "DOOR"        # current page name
    sd_manual_page: str = ""     # pilot-selected page ("" = auto)
    sd_data: dict = field(default_factory=dict)     # page payload
    cleared_ids: list = field(default_factory=list)


@dataclass
class SimMeta:
    time_s: float = 0.0
    paused: bool = False
    accel: int = 1
    situation: str = "cruise"


@dataclass
class SimState:
    fdm: FdmState
    ctl: ControlsState = field(default_factory=ControlsState)
    fcu: FcuState = field(default_factory=FcuState)
    fma: FmaState = field(default_factory=FmaState)
    guidance: GuidanceState = field(default_factory=GuidanceState)
    radio: RadioState = field(default_factory=RadioState)
    fms: FmsState = field(default_factory=FmsState)
    elec: ElecState = field(default_factory=ElecState)
    hyd: HydState = field(default_factory=HydState)
    fuel: FuelState = field(default_factory=FuelState)
    bleed: BleedState = field(default_factory=BleedState)
    press: PressState = field(default_factory=PressState)
    apu: ApuState = field(default_factory=ApuState)
    eng: EngState = field(default_factory=EngState)
    fctl: FctlState = field(default_factory=FctlState)
    ecam: EcamState = field(default_factory=EcamState)
    sim: SimMeta = field(default_factory=SimMeta)
