// Boot: connect, size the PFD, run the render loop, wire the FCU strip.

import { SimLink } from "./ws.js";
import { bindKeyboard } from "./keyboard.js";
import { setupCanvas } from "./lib/gfx.js";
import { renderPFD, PFD_W, PFD_H } from "./displays/pfd.js";
import { renderND, ND_W, ND_H } from "./displays/nd.js";
import { renderEWD, EWD_W, EWD_H } from "./displays/ewd.js";
import { renderSD, SD_W, SD_H } from "./displays/sd.js";
import { buildMcdu } from "./panels/mcdu.js";
import { buildOverhead } from "./panels/overhead.js";

const link = new SimLink(`ws://${location.host}/ws`);
bindKeyboard(link);

const conn = document.getElementById("conn");
link.onstatus = () => {
  conn.textContent = link.connected ? "CONNECTED" : "RECONNECTING…";
  conn.className = link.connected ? "ok" : "warn";
};

const pfdCtx = setupCanvas(document.getElementById("pfd"), PFD_W, PFD_H);
const ndCtx = setupCanvas(document.getElementById("nd"), ND_W, ND_H);
const ewdCtx = setupCanvas(document.getElementById("ewd"), EWD_W, EWD_H);
const sdCtx = setupCanvas(document.getElementById("sd"), SD_W, SD_H);
const mcdu = buildMcdu(document.getElementById("mcdu"), link);
const overhead = buildOverhead(document.getElementById("ovhd"), link);

const efis = { mode: "arc", range: 40 };
document.getElementById("nd-mode").onchange = (e) => (efis.mode = e.target.value);
document.getElementById("nd-range").onchange = (e) => (efis.range = Number(e.target.value));

// side panel tabs
const tabs = { mcdu: document.getElementById("tab-mcdu"),
               ovhd: document.getElementById("tab-ovhd") };
const panes = { mcdu: document.getElementById("mcdu"),
                ovhd: document.getElementById("ovhd") };
for (const key of Object.keys(tabs)) {
  tabs[key].onclick = () => {
    for (const k of Object.keys(tabs)) {
      tabs[k].classList.toggle("on", k === key);
      panes[k].hidden = k !== key;
    }
  };
}

// ECAM keys + master lights
const mwBtn = document.getElementById("mw");
const mcBtn = document.getElementById("mc");
mwBtn.onclick = () => link.cmd("ecam.warning_cancel");
mcBtn.onclick = () => link.cmd("ecam.clr");
for (const btn of document.querySelectorAll("#ecam-keys button[data-page]")) {
  btn.onclick = () => link.cmd("ecam.page", btn.dataset.page);
}
document.getElementById("ecam-clr").onclick = () => link.cmd("ecam.clr");
document.getElementById("ecam-rcl").onclick = () => link.cmd("ecam.rcl");

// --- FCU strip -----------------------------------------------------------------
const fields = {
  spd: document.getElementById("fcu-spd"),
  hdg: document.getElementById("fcu-hdg"),
  alt: document.getElementById("fcu-alt"),
  vs: document.getElementById("fcu-vs"),
};
for (const [key, el] of Object.entries(fields)) {
  el.addEventListener("change", () => {
    if (el.value !== "") link.cmd(`fcu.${key}.set`, Number(el.value));
  });
  // scroll wheel rotates the knob
  el.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const step = key === "alt" ? 100 : key === "vs" ? 100 : 1;
    const cur = Number(el.value || 0);
    link.cmd(`fcu.${key}.set`, cur + (ev.deltaY < 0 ? step : -step));
  }, { passive: false });
}
for (const btn of document.querySelectorAll(".knob")) {
  btn.addEventListener("click", () => link.cmd(btn.dataset.cmd));
}
const ap1Btn = document.getElementById("fcu-ap1");
const athrBtn = document.getElementById("fcu-athr");
const fdBtn = document.getElementById("fcu-fd");
const pauseBtn = document.getElementById("pause-btn");
const detentEl = document.getElementById("detent");
ap1Btn.onclick = () => link.cmd("fcu.ap1.toggle");
athrBtn.onclick = () => link.cmd("fcu.athr.toggle");
fdBtn.onclick = () => link.cmd("fcu.fd.toggle");
pauseBtn.onclick = () => link.cmd("sim.pause");

function syncPanel(s) {
  const f = s.fcu;
  if (document.activeElement !== fields.spd) {
    fields.spd.value = f.spd_mach ? f.spd : Math.round(f.spd);
  }
  if (document.activeElement !== fields.hdg) fields.hdg.value = f.hdg;
  if (document.activeElement !== fields.alt) fields.alt.value = f.alt;
  if (document.activeElement !== fields.vs) fields.vs.value = f.vs ?? "";
  ap1Btn.classList.toggle("on", f.ap1);
  athrBtn.classList.toggle("on", f.athr);
  fdBtn.classList.toggle("on", f.fd);
  pauseBtn.classList.toggle("on", s.sim.paused);
  detentEl.textContent = s.ctl.detent === "MAN"
    ? `${Math.round(s.ctl.thrust_man * 100)}%` : s.ctl.detent;
  if (link.syncFromSnap) link.syncFromSnap(s);
}

const simstat = document.getElementById("simstat");

// --- render loop --------------------------------------------------------------
let lastMcduRender = "";
let lastOvhdRender = 0;
function frame() {
  const s = link.view();
  if (s) {
    renderPFD(pfdCtx, s);
    renderND(ndCtx, s, efis);
    renderEWD(ewdCtx, s);
    renderSD(sdCtx, s);
    const mcduKey = JSON.stringify(s.fms.mcdu.lines);
    if (mcduKey !== lastMcduRender) {
      lastMcduRender = mcduKey;
      mcdu.update(s.fms);
    }
    if (performance.now() - lastOvhdRender > 250) {
      lastOvhdRender = performance.now();
      overhead.update(s);
      mwBtn.classList.toggle("active", s.ecam.mw);
      mcBtn.classList.toggle("active", s.ecam.mc);
      const page = s.ecam.sd_page;
      for (const btn of document.querySelectorAll("#ecam-keys button[data-page]")) {
        btn.classList.toggle("on", btn.dataset.page === page && s.ecam.sd_manual);
      }
    }
    syncPanel(s);
    simstat.textContent =
      `t=${s.time.toFixed(0)}s  GS ${s.fdm.gs.toFixed(0)}  ` +
      `N1 ${s.eng[0].n1.toFixed(0)}/${s.eng[1].n1.toFixed(0)}  ` +
      `FUEL ${s.fuel.total.toFixed(0)} lbs` +
      (s.sim.paused ? "  ‖ PAUSED" : "") +
      (s.sim.accel > 1 ? `  »${s.sim.accel}x` : "");
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
