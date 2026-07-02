"""WebSocket protocol: snapshot builder and message schema.

Server -> client:  {"t": "snap", ...}   at SNAPSHOT_HZ
Client -> server:  {"t": "cmd", "name": "<dotted.name>", "value": ...}

Snapshots include body/path rates so the client can dead-reckon between
frames and render smoothly at display refresh rate.
"""

from __future__ import annotations

from ikarus.core.state import SimState
from ikarus.nav import geo

PROTOCOL_VERSION = 4


def build_snapshot(state: SimState, failures=None) -> dict:
    fdm, ctl, meta = state.fdm, state.ctl, state.sim
    fcu, fma, guidance = state.fcu, state.fma, state.guidance
    radio, fms = state.radio, state.fms
    eng, ecam = state.eng, state.ecam
    return {
        "t": "snap",
        "v": PROTOCOL_VERSION,
        "time": round(meta.time_s, 3),
        "fdm": {
            "lat": fdm.lat_deg,
            "lon": fdm.lon_deg,
            "alt": round(fdm.alt_ft, 1),
            "agl": round(fdm.agl_ft, 1),
            "pitch": round(fdm.pitch_deg, 2),
            "roll": round(fdm.roll_deg, 2),
            "hdg": round(fdm.hdg_true_deg, 2),
            "cas": round(fdm.cas_kts, 1),
            "tas": round(fdm.tas_kts, 1),
            "gs": round(fdm.gs_kts, 1),
            "mach": round(fdm.mach, 3),
            "vs": round(fdm.vs_fpm, 0),
            "alpha": round(fdm.alpha_deg, 2),
            "track": round(fdm.track_true_deg, 2),
            "wow": fdm.wow,
            "magvar": round(geo.magvar_deg(fdm.lat_deg, fdm.lon_deg), 1),
            # rates for client-side dead reckoning
            "p": round(fdm.p_rps, 4),
            "q": round(fdm.q_rps, 4),
            "r": round(fdm.r_rps, 4),
        },
        "eng": [
            {
                "n1": round(eng.n1[i], 1),
                "n2": round(eng.n2[i], 1),
                "egt": round(eng.egt_c[i]),
                "ff": round(eng.ff_pph[i]),
                "thrust": round(fdm.engines[i].thrust_lbs, 0),
                "running": eng.running[i],
                "phase": eng.phase[i],
                "master": eng.master[i],
            }
            for i in range(2)
        ],
        "eng_mode": eng.mode,
        "fuel": {"total": round(state.fuel.total_lbs, 0)},
        "ctl": {
            "flaps": ctl.flaps_setting,
            "gear": ctl.gear_down,
            "spdbrk": round(ctl.speedbrake, 2),
            "detent": ctl.thrust_detent,
            "thrust_man": round(ctl.thrust_manual, 2),
            "pbrk": ctl.parking_brake,
        },
        "fcu": {
            "spd": round(fcu.spd_kts, 3 if fcu.spd_is_mach else 0),
            "spd_mach": fcu.spd_is_mach,
            "spd_managed": fcu.spd_managed,
            "hdg": round(fcu.hdg_deg),
            "hdg_managed": fcu.hdg_managed,
            "alt": round(fcu.alt_ft),
            "vs": None if fcu.vs_fpm is None else round(fcu.vs_fpm),
            "ap1": fcu.ap1,
            "fd": fcu.fd,
            "athr": fcu.athr,
        },
        "fma": {
            "thr": fma.thrust,
            "thr_man": fma.thrust_man,
            "vert": fma.vertical,
            "vert_armed": fma.vertical_armed,
            "lat": fma.lateral,
            "lat_armed": fma.lateral_armed,
            "ap": fma.ap,
            "fd": fma.fd,
            "athr": fma.athr,
            "athr_active": fma.athr_active,
        },
        "guidance": {
            "fd_pitch": round(guidance.pitch_target_deg, 2),
            "fd_roll": round(guidance.roll_target_deg, 2),
            "tgt_cas": round(guidance.target_cas_kts, 1),
            "law": guidance.law,
        },
        "radio": {
            "nav1": {"freq": radio.nav1_freq_khz, "id": radio.nav1_ident,
                     "brg": round(radio.nav1_bearing_mag, 1),
                     "dme": radio.nav1_dme_nm, "ok": radio.nav1_ok},
            "nav2": {"freq": radio.nav2_freq_khz, "id": radio.nav2_ident,
                     "brg": round(radio.nav2_bearing_mag, 1),
                     "dme": radio.nav2_dme_nm, "ok": radio.nav2_ok},
            "ils": {"ok": radio.ils_ok, "id": radio.ils_ident,
                    "crs": round(radio.ils_course_mag),
                    "loc": round(radio.ils_loc_dots, 2),
                    "gs": round(radio.ils_gs_dots, 2),
                    "dme": radio.ils_dme_nm},
        },
        "fms": {
            "origin": fms.origin, "dest": fms.dest,
            "sid": fms.sid, "star": fms.star, "appr": fms.approach,
            "dep_rwy": fms.dep_runway, "arr_rwy": fms.arr_runway,
            "active_idx": fms.active_idx,
            "plan_version": fms.plan_version,
            "legs": [
                {"id": leg.ident, "lat": round(leg.lat, 5),
                 "lon": round(leg.lon, 5),
                 "aa": leg.alt_above, "ab": leg.alt_below, "spd": leg.speed}
                for leg in fms.legs
            ],
            "xtk": round(fms.xtk_nm, 2),
            "crs": round(fms.course_mag),
            "dtg": round(fms.dtg_nm, 1),
            "dist_dest": round(fms.dist_to_dest_nm, 1),
            "tod": round(fms.tod_dist_nm, 1),
            "vdev": round(fms.vdev_ft),
            "mcdu": {
                "page": fms.mcdu_page,
                "lines": fms.mcdu_lines,
            },
        },
        "ecam": {
            "mw": ecam.master_warning,
            "mc": ecam.master_caution,
            "phase": ecam.flight_phase,
            "alerts": [
                {"id": a.id, "level": a.level, "lines": a.lines}
                for a in ecam.alerts if a.id not in ecam.cleared_ids
            ],
            "memos": ecam.memos,
            "sd_page": ecam.sd_page,
            "sd_manual": bool(ecam.sd_manual_page),
            "sd": ecam.sd_data,
        },
        "ovhd": {
            "elec": {
                "bat1": state.elec.bat1, "bat2": state.elec.bat2,
                "ext_pwr": state.elec.ext_pwr,
                "ext_avail": state.elec.ext_pwr_avail,
                "gen1": state.elec.gen1, "gen2": state.elec.gen2,
                "apu_gen": state.elec.apu_gen,
                "ac1": state.elec.ac1, "ac2": state.elec.ac2,
            },
            "apu": {"master": state.apu.master, "avail": state.apu.avail,
                    "state": state.apu.state, "n": round(state.apu.n_pct)},
            "fuel": {"l1": state.fuel.pump_l1, "l2": state.fuel.pump_l2,
                     "c1": state.fuel.pump_c1, "c2": state.fuel.pump_c2,
                     "r1": state.fuel.pump_r1, "r2": state.fuel.pump_r2,
                     "xfeed": state.fuel.xfeed},
            "hyd": {"eng1": state.hyd.eng1_pump, "eng2": state.hyd.eng2_pump,
                    "blue": state.hyd.blue_elec_pump,
                    "yellow": state.hyd.yellow_elec_pump,
                    "ptu": state.hyd.ptu_auto},
            "bleed": {"eng1": state.bleed.eng1_bleed,
                      "eng2": state.bleed.eng2_bleed,
                      "apu": state.bleed.apu_bleed,
                      "xbleed": state.bleed.xbleed,
                      "pack1": state.bleed.pack1, "pack2": state.bleed.pack2},
        },
        "press": {
            "cab_alt": round(state.press.cabin_alt_ft),
            "cab_vs": round(state.press.cabin_vs_fpm),
            "dp": round(state.press.delta_p_psi, 1),
        },
        "law": state.fctl.law,
        "failures": failures.active_ids if failures else [],
        "sim": {"paused": meta.paused, "accel": meta.accel},
    }
