// Engine/Warning Display: N1/EGT gauges, FF, flaps, alerts + memos.

import { C, text, line, poly } from "../lib/gfx.js";

export const EWD_W = 500;
export const EWD_H = 500;

export function renderEWD(ctx, s) {
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, EWD_W, EWD_H);

  for (let i = 0; i < 2; i++) {
    const x = 140 + i * 220;
    drawN1(ctx, x, 80, s.eng[i]);
    drawEGT(ctx, x, 185, s.eng[i]);
    text(ctx, s.eng[i].n2.toFixed(1), x, 245, { size: 15, color: C.green });
    text(ctx, `${s.eng[i].ff}`, x, 275, { size: 15, color: C.green });
    if (s.eng[i].phase !== "RUNNING" && s.eng[i].phase !== "OFF") {
      text(ctx, s.eng[i].phase, x, 40, { size: 12, color: C.cyan });
    }
  }
  text(ctx, "N1 %", 250, 80, { size: 12, color: C.cyan });
  text(ctx, "EGT °C", 250, 185, { size: 12, color: C.cyan });
  text(ctx, "N2 %", 250, 245, { size: 12, color: C.cyan });
  text(ctx, "FF PPH", 250, 275, { size: 12, color: C.cyan });

  // flaps + detent line
  line(ctx, 20, 300, 480, 300, C.gray, 1);
  const flapNames = ["0", "1", "2", "3", "FULL"];
  text(ctx, `FLAPS ${flapNames[s.ctl.flaps]}`, 400, 320,
       { size: 14, color: C.green });
  text(ctx, `${s.ctl.detent}`, 90, 320, { size: 14, color: C.white });
  if (s.ctl.gear) text(ctx, "GEAR DN", 250, 320, { size: 13, color: C.green });

  // alerts (left) and memos (right)
  line(ctx, 250, 335, 250, 495, C.gray, 1);
  let y = 350;
  const colors = { r: C.red, a: C.amber, c: C.cyan, g: C.green, w: C.white };
  for (const alert of s.ecam.alerts.slice(0, 4)) {
    for (const [txt, col] of alert.lines.slice(0, 3)) {
      text(ctx, txt, 16, y, { size: 13, color: colors[col] || C.white,
                              align: "left" });
      y += 17;
      if (y > 485) break;
    }
    if (y > 485) break;
  }
  y = 350;
  for (const [txt, col] of s.ecam.memos.slice(0, 8)) {
    text(ctx, txt, 264, y, { size: 13, color: colors[col] || C.green,
                             align: "left" });
    y += 17;
  }

  window.__ikarusDebug = window.__ikarusDebug || {};
  window.__ikarusDebug.ewd = {
    n1: s.eng.map((e) => e.n1),
    alerts: s.ecam.alerts.map((a) => a.id),
    memos: s.ecam.memos.map((m) => m[0]),
  };
}

function drawN1(ctx, cx, cy, eng) {
  drawArcGauge(ctx, cx, cy, 45, eng.n1, 110, eng.n1.toFixed(1), C.green);
}

function drawEGT(ctx, cx, cy, eng) {
  drawArcGauge(ctx, cx, cy, 38, eng.egt / 10, 100, `${eng.egt}`,
               eng.egt > 900 ? C.red : C.green);
}

// simple 210-degree arc gauge: value 0..max mapped over the sweep
function drawArcGauge(ctx, cx, cy, r, value, max, label, color) {
  const start = Math.PI * 0.75;
  const sweep = Math.PI * 1.17;
  ctx.strokeStyle = C.white;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, r, start, start + sweep);
  ctx.stroke();
  const frac = Math.max(0, Math.min(1, value / max));
  const a = start + sweep * frac;
  line(ctx, cx, cy, cx + Math.cos(a) * (r - 2), cy + Math.sin(a) * (r - 2),
       color, 3);
  // red tick at limit
  const alim = start + sweep * 0.92;
  line(ctx, cx + Math.cos(alim) * (r - 6), cy + Math.sin(alim) * (r - 6),
       cx + Math.cos(alim) * (r + 4), cy + Math.sin(alim) * (r + 4), C.red, 3);
  ctx.fillStyle = C.bg;
  ctx.fillRect(cx - 30, cy + 6, 60, 20);
  text(ctx, label, cx, cy + 16, { size: 15, color });
}
