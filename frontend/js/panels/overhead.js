// Overhead + pedestal panel: pushbutton switches wired to ovhd.*/eng.* commands.
// Buttons reflect state from snapshots (on/off/avail/fault classes).

const LAYOUT = [
  ["ELEC", [
    ["BAT 1", "ovhd.elec.bat1", (o) => o.elec.bat1],
    ["BAT 2", "ovhd.elec.bat2", (o) => o.elec.bat2],
    ["EXT PWR", "ovhd.elec.ext_pwr", (o) => o.elec.ext_pwr,
     (o) => o.elec.ext_avail && !o.elec.ext_pwr ? "AVAIL" : ""],
    ["GEN 1", "ovhd.elec.gen1", (o) => o.elec.gen1],
    ["GEN 2", "ovhd.elec.gen2", (o) => o.elec.gen2],
    ["APU GEN", "ovhd.elec.apu_gen", (o) => o.elec.apu_gen],
  ]],
  ["APU", [
    ["MASTER", "ovhd.apu.master", (o) => o.apu.master],
    ["START", "ovhd.apu.start", (o) => o.apu.state === "START",
     (o) => o.apu.avail ? "AVAIL" : ""],
  ]],
  ["FUEL", [
    ["L PMP 1", "ovhd.fuel.pump_l1", (o) => o.fuel.l1],
    ["L PMP 2", "ovhd.fuel.pump_l2", (o) => o.fuel.l2],
    ["CTR 1", "ovhd.fuel.pump_c1", (o) => o.fuel.c1],
    ["CTR 2", "ovhd.fuel.pump_c2", (o) => o.fuel.c2],
    ["R PMP 1", "ovhd.fuel.pump_r1", (o) => o.fuel.r1],
    ["R PMP 2", "ovhd.fuel.pump_r2", (o) => o.fuel.r2],
    ["X FEED", "ovhd.fuel.xfeed", (o) => o.fuel.xfeed],
  ]],
  ["HYD", [
    ["ENG 1 PMP", "ovhd.hyd.eng1_pump", (o) => o.hyd.eng1],
    ["ENG 2 PMP", "ovhd.hyd.eng2_pump", (o) => o.hyd.eng2],
    ["BLUE ELEC", "ovhd.hyd.blue", (o) => o.hyd.blue],
    ["YEL ELEC", "ovhd.hyd.yellow", (o) => o.hyd.yellow],
    ["PTU", "ovhd.hyd.ptu", (o) => o.hyd.ptu],
  ]],
  ["AIR", [
    ["BLEED 1", "ovhd.bleed.eng1", (o) => o.bleed.eng1],
    ["BLEED 2", "ovhd.bleed.eng2", (o) => o.bleed.eng2],
    ["APU BLEED", "ovhd.bleed.apu", (o) => o.bleed.apu],
    ["PACK 1", "ovhd.bleed.pack1", (o) => o.bleed.pack1],
    ["PACK 2", "ovhd.bleed.pack2", (o) => o.bleed.pack2],
  ]],
];

const XBLEED_CYCLE = { AUTO: "OPEN", OPEN: "SHUT", SHUT: "AUTO" };
const ENG_MODES = { NORM: "IGN_START", IGN_START: "NORM" };

export function buildOverhead(container, link) {
  container.innerHTML = "";
  const updaters = [];

  for (const [section, buttons] of LAYOUT) {
    const box = document.createElement("fieldset");
    box.className = "ovhd-section";
    const legend = document.createElement("legend");
    legend.textContent = section;
    box.appendChild(legend);
    for (const [label, cmd, isOn, sub] of buttons) {
      const b = document.createElement("button");
      b.className = "ovhd-btn";
      b.innerHTML = `<span>${label}</span><em></em>`;
      b.onclick = () => link.cmd(cmd);
      box.appendChild(b);
      updaters.push((o) => {
        b.classList.toggle("on", !!isOn(o));
        b.querySelector("em").textContent =
          (sub && sub(o)) || (isOn(o) ? "ON" : "OFF");
      });
    }
    container.appendChild(box);
  }

  // X-bleed selector + engine panel
  const eng = document.createElement("fieldset");
  eng.className = "ovhd-section";
  eng.innerHTML = "<legend>ENG / X BLEED</legend>";
  const xb = document.createElement("button");
  xb.className = "ovhd-btn";
  xb.innerHTML = "<span>X BLEED</span><em>AUTO</em>";
  let xbleedState = "AUTO";
  xb.onclick = () => link.cmd("ovhd.bleed.xbleed", XBLEED_CYCLE[xbleedState]);
  eng.appendChild(xb);
  const mode = document.createElement("button");
  mode.className = "ovhd-btn";
  mode.innerHTML = "<span>ENG MODE</span><em>NORM</em>";
  let modeState = "NORM";
  mode.onclick = () => link.cmd("eng.mode", ENG_MODES[modeState] || "NORM");
  eng.appendChild(mode);
  const masters = [];
  for (const i of [1, 2]) {
    const m = document.createElement("button");
    m.className = "ovhd-btn master";
    m.innerHTML = `<span>MASTER ${i}</span><em>OFF</em>`;
    m.onclick = () => link.cmd(`eng.master${i}`);
    eng.appendChild(m);
    masters.push(m);
  }
  container.appendChild(eng);

  return {
    update(snap) {
      const o = snap.ovhd;
      for (const u of updaters) u(o);
      xbleedState = o.bleed.xbleed;
      xb.querySelector("em").textContent = xbleedState;
      modeState = snap.eng_mode;
      mode.querySelector("em").textContent = modeState;
      mode.classList.toggle("on", modeState !== "NORM");
      snap.eng.forEach((e, i) => {
        masters[i].classList.toggle("on", e.master);
        masters[i].querySelector("em").textContent =
          e.master ? (e.running ? "RUN" : e.phase) : "OFF";
      });
    },
  };
}
