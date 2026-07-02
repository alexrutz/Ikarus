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
    sim: SimMeta = field(default_factory=SimMeta)
