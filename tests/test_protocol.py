"""Snapshot schema and WebSocket round-trip tests."""

import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ikarus.net.protocol import build_snapshot
from ikarus.net.server import make_app


def test_snapshot_shape(sim):
    sim.run_for(1)
    snap = build_snapshot(sim.state)
    assert snap["t"] == "snap"
    assert snap["v"] == 4
    for key in ("ecam", "ovhd", "press", "law"):
        assert key in snap, f"missing snapshot section {key}"
    # keys the frontend contracts on
    for key in ("fdm", "eng", "fuel", "ctl", "fcu", "fma", "guidance", "sim"):
        assert key in snap, f"missing snapshot section {key}"
    for key in ("lat", "lon", "alt", "pitch", "roll", "hdg", "cas",
                "vs", "mach", "p", "q", "r", "wow", "track"):
        assert key in snap["fdm"], f"missing fdm field {key}"
    for key in ("spd", "hdg", "alt", "vs", "ap1", "fd", "athr"):
        assert key in snap["fcu"], f"missing fcu field {key}"
    for key in ("thr", "vert", "lat", "ap", "athr"):
        assert key in snap["fma"], f"missing fma field {key}"
    assert len(snap["eng"]) == 2
    assert json.dumps(snap)  # serializable


def test_snapshot_values_sane(sim):
    sim.run_for(1)
    snap = build_snapshot(sim.state)
    assert 30000 < snap["fdm"]["alt"] < 36000
    assert snap["eng"][0]["running"] is True
    assert snap["fcu"]["ap1"] is True


@pytest.mark.asyncio
async def test_ws_command_roundtrip(sim):
    """Connect a WS client, send a command, observe it in the snapshot."""
    app = make_app(sim)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        ws = await client.ws_connect("/ws")
        await ws.send_json({"t": "cmd", "name": "fcu.hdg.set", "value": 123})
        snap = None
        for _ in range(30):  # snapshots arrive at 15 Hz
            msg = await ws.receive_json(timeout=2)
            if msg.get("t") == "snap":
                snap = msg
                if snap["fcu"]["hdg"] == 123:
                    break
        assert snap is not None
        assert snap["fcu"]["hdg"] == 123
        # unknown command -> error reply, connection stays up
        await ws.send_json({"t": "cmd", "name": "no.such.cmd"})
        while True:
            msg = await ws.receive_json(timeout=2)
            if msg.get("t") == "err":
                break
        await ws.close()
    finally:
        await client.close()
