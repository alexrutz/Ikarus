"""WebSocket protocol: snapshot builder and message schema.

Server -> client:  {"t": "snap", ...}   at SNAPSHOT_HZ
Client -> server:  {"t": "cmd", "name": "<dotted.name>", "value": ...}

Snapshots include body/path rates so the client can dead-reckon between
frames and render smoothly at display refresh rate.
"""

from __future__ import annotations

from ikarus.core.state import SimState

PROTOCOL_VERSION = 1


def build_snapshot(state: SimState) -> dict:
    fdm, ctl, ap, meta = state.fdm, state.ctl, state.ap, state.sim
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
            # rates for client-side dead reckoning
            "p": round(fdm.p_rps, 4),
            "q": round(fdm.q_rps, 4),
            "r": round(fdm.r_rps, 4),
        },
        "eng": [
            {
                "n1": round(e.n1, 1),
                "n2": round(e.n2, 1),
                "ff": round(e.fuel_flow_pph, 0),
                "thrust": round(e.thrust_lbs, 0),
                "running": e.running,
            }
            for e in fdm.engines
        ],
        "fuel": {"total": round(fdm.total_fuel_lbs, 0)},
        "ctl": {
            "flaps": ctl.flaps_setting,
            "gear": ctl.gear_down,
            "spdbrk": round(ctl.speedbrake, 2),
            "thrust": round(ctl.thrust_lever, 2),
            "pbrk": ctl.parking_brake,
        },
        "ap": {
            "ap": ap.ap_engaged,
            "athr": ap.athr_engaged,
            "hdg": round(ap.sel_hdg_deg),
            "alt": round(ap.sel_alt_ft),
            "spd": round(ap.sel_spd_kts),
            "vs": round(ap.sel_vs_fpm),
        },
        "sim": {"paused": meta.paused, "accel": meta.accel},
    }
