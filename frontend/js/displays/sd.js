// System Display: one renderer per page, driven by snap.ecam.sd.

import { C, text, line } from "../lib/gfx.js";

export const SD_W = 500;
export const SD_H = 500;

export function renderSD(ctx, s) {
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, SD_W, SD_H);
  const page = s.ecam.sd_page;
  const d = s.ecam.sd;
  text(ctx, page, 250, 22, { size: 18, color: C.white, bold: true });
  line(ctx, 150, 34, 350, 34, C.white, 1.5);

  const render = PAGES[page];
  if (render && d) render(ctx, d, s);

  // permanent data footer
  line(ctx, 10, 460, 490, 460, C.gray, 1);
  text(ctx, `SAT ${Math.round(15 - 1.98 * s.fdm.alt / 1000)}°C`, 70, 480,
       { size: 12, color: C.green });
  text(ctx, `GW ${Math.round((s.fuel.total + 112000) / 100) * 100} LBS`, 250, 480,
       { size: 12, color: C.green });
  text(ctx, `${new Date(s.time * 1000).toISOString().substr(11, 5)}`, 430, 480,
       { size: 12, color: C.green });

  window.__ikarusDebug = window.__ikarusDebug || {};
  window.__ikarusDebug.sd = { page };
}

function onoff(v, on = "ON", off = "OFF") { return v ? on : off; }
function pw(v) { return v ? C.green : C.amber; }

function kv(ctx, x, y, label, value, color = C.green, size = 14) {
  text(ctx, label, x, y, { size: 12, color: C.white, align: "left" });
  text(ctx, `${value}`, x + 8, y + 20, { size, color, align: "left" });
}

const PAGES = {
  ELEC(ctx, d) {
    // batteries and generators top, buses bottom
    kv(ctx, 30, 60, "BAT 1", `${d.bat1.v} V`, d.bat1.on ? C.green : C.amber);
    kv(ctx, 400, 60, "BAT 2", `${d.bat2.v} V`, d.bat2.on ? C.green : C.amber);
    kv(ctx, 30, 130, "GEN 1", d.gen1.fault ? "FAULT" :
       (d.gen1.on ? `${d.gen1.load}%` : "OFF"),
       d.gen1.fault ? C.amber : pw(d.gen1.on));
    kv(ctx, 400, 130, "GEN 2", d.gen2.fault ? "FAULT" :
       (d.gen2.on ? `${d.gen2.load}%` : "OFF"),
       d.gen2.fault ? C.amber : pw(d.gen2.on));
    kv(ctx, 215, 100, "APU GEN", d.apu_gen.avail
       ? `${d.apu_gen.load}%` : "OFF", pw(d.apu_gen.avail));
    kv(ctx, 215, 170, "EXT PWR", d.ext.on ? "ON" :
       (d.ext.avail ? "AVAIL" : "----"), d.ext.on ? C.green : C.white);
    // buses
    const buses = [["AC 1", d.ac1, 70], ["AC ESS", d.ac_ess, 250],
                   ["AC 2", d.ac2, 430]];
    for (const [name, powered, x] of buses) {
      ctx.strokeStyle = powered ? C.green : C.amber;
      ctx.lineWidth = 2;
      ctx.strokeRect(x - 45, 250, 90, 28);
      text(ctx, name, x, 264, { size: 14, color: powered ? C.green : C.amber });
    }
    const dcs = [["DC 1", d.dc1, 70], ["DC BAT", d.dc_bat, 175],
                 ["DC ESS", d.dc_ess, 320], ["DC 2", d.dc2, 430]];
    for (const [name, powered, x] of dcs) {
      ctx.strokeRect(x - 42, 320, 84, 26);
      ctx.strokeStyle = powered ? C.green : C.amber;
      text(ctx, name, x, 333, { size: 13, color: powered ? C.green : C.amber });
    }
    text(ctx, `AC1 ← ${d.ac1_src || "----"}`, 70, 390, { size: 12, color: C.white });
    text(ctx, `AC2 ← ${d.ac2_src || "----"}`, 430, 390, { size: 12, color: C.white });
  },

  HYD(ctx, d) {
    const systems = [["GREEN", d.green, d.g_qty, 90],
                     ["BLUE", d.blue, d.b_qty, 250],
                     ["YELLOW", d.yellow, d.y_qty, 410]];
    for (const [name, psi, qty, x] of systems) {
      const ok = psi > 1450;
      text(ctx, name, x, 70, { size: 14, color: ok ? C.white : C.amber });
      // vertical pressure bar
      const h = 140 * Math.min(1, psi / 3000);
      ctx.fillStyle = ok ? C.green : C.amber;
      ctx.fillRect(x - 7, 230 - h, 14, h);
      ctx.strokeStyle = C.white;
      ctx.strokeRect(x - 9, 88, 18, 144);
      text(ctx, `${psi}`, x, 250, { size: 15, color: ok ? C.green : C.amber });
      text(ctx, `QTY ${(qty * 100).toFixed(0)}%`, x, 280,
           { size: 11, color: qty > 0.2 ? C.green : C.amber });
    }
    kv(ctx, 60, 320, "ENG 1 PUMP", onoff(d.eng1_pump), pw(d.eng1_pump));
    kv(ctx, 210, 320, "B ELEC PUMP", onoff(d.blue_pump), pw(d.blue_pump));
    kv(ctx, 380, 320, "ENG 2 PUMP", onoff(d.eng2_pump), pw(d.eng2_pump));
    text(ctx, d.ptu ? "PTU RUNNING" : "PTU", 250, 400,
         { size: 14, color: d.ptu ? C.green : C.white });
    if (d.rat) text(ctx, "RAT OUT", 250, 425, { size: 13, color: C.green });
  },

  FUEL(ctx, d) {
    const tanks = [["OUTER L", d.outer_l, 55], ["INNER L", d.inner_l, 155],
                   ["CTR", d.center, 250], ["INNER R", d.inner_r, 345],
                   ["OUTER R", d.outer_r, 445]];
    for (const [name, lbs, x] of tanks) {
      ctx.strokeStyle = C.white;
      ctx.strokeRect(x - 44, 90, 88, 60);
      text(ctx, name, x, 78, { size: 11, color: C.white });
      text(ctx, `${lbs}`, x, 120, { size: 14, color: C.green });
    }
    text(ctx, `TOTAL ${d.total} LBS`, 250, 190, { size: 15, color: C.green });
    const pumps = [["L1", d.pumps.l1, 130], ["L2", d.pumps.l2, 180],
                   ["C1", d.pumps.c1, 225], ["C2", d.pumps.c2, 275],
                   ["R1", d.pumps.r1, 320], ["R2", d.pumps.r2, 370]];
    for (const [name, on, x] of pumps) {
      ctx.strokeStyle = on ? C.green : C.amber;
      ctx.lineWidth = 2;
      ctx.strokeRect(x - 18, 230, 36, 24);
      text(ctx, name, x, 242, { size: 12, color: on ? C.green : C.amber });
    }
    text(ctx, d.xfeed ? "X FEED OPEN" : "X FEED SHUT", 250, 300,
         { size: 13, color: d.xfeed ? C.green : C.white });
    if (!d.l_press) text(ctx, "L PUMPS LO PR", 130, 330, { size: 12, color: C.amber });
    if (!d.r_press) text(ctx, "R PUMPS LO PR", 370, 330, { size: 12, color: C.amber });
  },

  BLEED(ctx, d) {
    kv(ctx, 80, 80, "ENG 1 BLEED", onoff(d.eng1), pw(d.eng1));
    kv(ctx, 360, 80, "ENG 2 BLEED", onoff(d.eng2), pw(d.eng2));
    kv(ctx, 90, 160, "DUCT 1", `${d.duct1} PSI`,
       d.duct1 > 10 ? C.green : C.amber);
    kv(ctx, 360, 160, "DUCT 2", `${d.duct2} PSI`,
       d.duct2 > 10 ? C.green : C.amber);
    kv(ctx, 215, 110, "APU BLEED", onoff(d.apu), pw(d.apu));
    text(ctx, `X BLEED ${d.xbleed} ${d.xbleed_open ? "(OPEN)" : "(SHUT)"}`,
         250, 250, { size: 13, color: C.green });
    line(ctx, 140, 190, d.xbleed_open ? 360 : 240, 190,
         d.xbleed_open ? C.green : C.gray, 3);
    kv(ctx, 100, 300, "PACK 1", d.pack1_flow ? "FLOW" : onoff(d.pack1),
       d.pack1_flow ? C.green : C.amber);
    kv(ctx, 340, 300, "PACK 2", d.pack2_flow ? "FLOW" : onoff(d.pack2),
       d.pack2_flow ? C.green : C.amber);
  },

  PRESS(ctx, d) {
    kv(ctx, 70, 90, "CAB ALT", `${d.cab_alt} FT`,
       d.cab_alt > 9550 ? C.red : C.green, 18);
    kv(ctx, 250, 90, "CAB V/S", `${d.cab_vs} FPM`, C.green, 16);
    kv(ctx, 400, 90, "ΔP", `${d.delta_p} PSI`, C.green, 18);
    kv(ctx, 70, 200, "OUTFLOW VALVE", `${Math.round(d.outflow * 100)}%`, C.green);
    kv(ctx, 300, 200, "LDG ELEV", `${d.ldg_elev} FT`, C.cyan);
  },

  APU(ctx, d) {
    kv(ctx, 120, 90, "N", `${d.n}%`, C.green, 20);
    kv(ctx, 320, 90, "EGT", `${d.egt}°C`, d.egt > 650 ? C.amber : C.green, 20);
    text(ctx, d.state + (d.avail ? "  (AVAIL)" : ""), 250, 180,
         { size: 16, color: d.avail ? C.green : C.white });
    kv(ctx, 120, 230, "GEN LOAD", `${d.gen_load}%`, C.green);
    kv(ctx, 300, 230, "BLEED", onoff(d.bleed), pw(d.bleed));
    if (d.flap) text(ctx, "FLAP OPEN", 250, 310, { size: 13, color: C.green });
  },

  ENG(ctx, d) {
    for (let i = 0; i < 2; i++) {
      const x = 130 + i * 240;
      text(ctx, `ENG ${i + 1}`, x, 66, { size: 14, color: C.white });
      kv(ctx, x - 50, 90, "N1", `${d.n1[i]}`, C.green);
      kv(ctx, x - 50, 140, "N2", `${d.n2[i]}`, C.green);
      kv(ctx, x - 50, 190, "EGT", `${d.egt[i]}°C`, C.green);
      kv(ctx, x - 50, 240, "FF", `${d.ff[i]} PPH`, C.green);
      text(ctx, d.phase[i], x, 320, { size: 13,
           color: d.phase[i] === "RUNNING" ? C.green : C.cyan });
    }
  },

  "F/CTL"(ctx, d) {
    text(ctx, `LAW: ${d.law.toUpperCase()}`, 250, 70,
         { size: 15, color: d.law === "normal" ? C.green : C.amber });
    const comp = [["ELAC", d.elac, 100], ["SEC", d.sec, 250], ["FAC", d.fac, 400]];
    for (const [name, arr, x] of comp) {
      text(ctx, name, x, 120, { size: 13, color: C.white });
      arr.forEach((ok, i) => {
        ctx.strokeStyle = ok ? C.green : C.amber;
        ctx.lineWidth = 2;
        ctx.strokeRect(x - 40 + i * 30, 135, 24, 22);
        text(ctx, `${i + 1}`, x - 28 + i * 30, 146,
             { size: 12, color: ok ? C.green : C.amber });
      });
    }
    kv(ctx, 80, 220, "ELEV", d.elev.toFixed(2), C.green);
    kv(ctx, 200, 220, "AIL", d.ail.toFixed(2), C.green);
    kv(ctx, 320, 220, "RUD", d.rud.toFixed(2), C.green);
    kv(ctx, 80, 290, "SPD BRK", d.spdbrk.toFixed(2), C.green);
    kv(ctx, 200, 290, "PITCH TRIM", d.pitch_trim.toFixed(2), C.green);
  },

  CRUISE(ctx, d) {
    kv(ctx, 100, 90, "FF 1", `${d.ff[0]} PPH`, C.green);
    kv(ctx, 320, 90, "FF 2", `${d.ff[1]} PPH`, C.green);
    kv(ctx, 100, 170, "FUEL", `${d.fuel_total} LBS`, C.green);
    kv(ctx, 320, 170, "CAB ALT", `${d.cab_alt} FT`, C.green);
    kv(ctx, 100, 250, "ΔP", `${d.delta_p} PSI`, C.green);
    kv(ctx, 320, 250, "SAT", `${d.sat_c}°C`, C.green);
  },
};
