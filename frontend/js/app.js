// Boot: connect, size the PFD, run the render loop, wire the AP strip.

import { SimLink } from "./ws.js";
import { bindKeyboard } from "./keyboard.js";
import { setupCanvas } from "./lib/gfx.js";
import { renderPFD, PFD_W, PFD_H } from "./displays/pfd.js";

const link = new SimLink(`ws://${location.host}/ws`);
bindKeyboard(link);

const conn = document.getElementById("conn");
link.onstatus = () => {
  conn.textContent = link.connected ? "CONNECTED" : "RECONNECTING…";
  conn.className = link.connected ? "ok" : "warn";
};

const pfdCtx = setupCanvas(document.getElementById("pfd"), PFD_W, PFD_H);

// --- provisional AP strip ----------------------------------------------------
const fields = {
  spd: document.getElementById("ap-spd"),
  hdg: document.getElementById("ap-hdg"),
  alt: document.getElementById("ap-alt"),
  vs: document.getElementById("ap-vs"),
};
for (const [key, el] of Object.entries(fields)) {
  el.addEventListener("change", () => link.cmd(`ap.${key}.set`, Number(el.value)));
}
const apBtn = document.getElementById("ap-btn");
const athrBtn = document.getElementById("athr-btn");
const pauseBtn = document.getElementById("pause-btn");
apBtn.onclick = () => link.cmd("ap.toggle");
athrBtn.onclick = () => link.cmd("athr.toggle");
pauseBtn.onclick = () => link.cmd("sim.pause");

function syncPanel(s) {
  for (const [key, el] of Object.entries(fields)) {
    if (document.activeElement !== el) el.value = s.ap[key];
  }
  apBtn.classList.toggle("on", s.ap.ap);
  athrBtn.classList.toggle("on", s.ap.athr);
  pauseBtn.classList.toggle("on", s.sim.paused);
  if (link.syncFromSnap) link.syncFromSnap(s);
}

const simstat = document.getElementById("simstat");

// --- render loop --------------------------------------------------------------
function frame() {
  const s = link.view();
  if (s) {
    renderPFD(pfdCtx, s);
    syncPanel(s);
    simstat.textContent =
      `t=${s.time.toFixed(0)}s  GS ${s.fdm.gs.toFixed(0)}  ` +
      `FUEL ${s.fuel.total.toFixed(0)} lbs` +
      (s.sim.paused ? "  ‖ PAUSED" : "") +
      (s.sim.accel > 1 ? `  »${s.sim.accel}x` : "");
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
