"""aiohttp application: serves the frontend statics and the /ws endpoint."""

from __future__ import annotations

import asyncio
import json
import logging

from aiohttp import WSMsgType, web

from ikarus import config
from ikarus.core.simloop import Sim, SimLoop
from ikarus.net.commands import CommandError
from ikarus.net.protocol import build_snapshot

log = logging.getLogger("ikarus.net")

SNAPSHOT_INTERVAL = 1.0 / config.SNAPSHOT_HZ


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    sim: Sim = request.app["sim"]
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    request.app["clients"].add(ws)
    log.info("client connected (%d total)", len(request.app["clients"]))
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                await ws.send_json({"t": "err", "msg": "bad json"})
                continue
            if data.get("t") == "cmd":
                try:
                    sim.cmd(data.get("name", ""), data.get("value"))
                except CommandError as e:
                    await ws.send_json({"t": "err", "msg": str(e)})
    finally:
        request.app["clients"].discard(ws)
        log.info("client disconnected (%d total)", len(request.app["clients"]))
    return ws


async def broadcast_snapshots(app: web.Application) -> None:
    sim: Sim = app["sim"]
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL)
        clients = app["clients"]
        if not clients:
            continue
        payload = json.dumps(build_snapshot(sim.state, sim.failures))
        for ws in list(clients):
            try:
                await ws.send_str(payload)
            except ConnectionError:
                clients.discard(ws)


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(config.FRONTEND_DIR / "index.html")


def make_app(sim: Sim) -> web.Application:
    app = web.Application()
    app["sim"] = sim
    app["clients"] = set()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_static("/static", config.FRONTEND_DIR)

    async def start_tasks(app: web.Application):
        loop = SimLoop(sim)
        app["simloop"] = loop
        app["tasks"] = [
            asyncio.create_task(loop.run()),
            asyncio.create_task(broadcast_snapshots(app)),
        ]
        yield
        loop.stop()
        for task in app["tasks"]:
            task.cancel()

    app.cleanup_ctx.append(start_tasks)
    return app


def run(situation: str = "cruise", port: int = 8080) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(message)s")
    sim = Sim(situation=situation)
    app = make_app(sim)
    log.info("Ikarus up: http://localhost:%d  (situation: %s)", port, situation)
    web.run_app(app, port=port, print=None)
