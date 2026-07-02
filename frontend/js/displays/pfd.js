// Primary Flight Display: attitude, speed/alt tapes, heading strip, V/S.
// Geometry is in a 500x500 CSS-pixel design space.

import { C, text, line, poly } from "../lib/gfx.js";

export const PFD_W = 500;
export const PFD_H = 500;

const ADI = { cx: 235, cy: 235, r: 130, pxPerDeg: 5.2 };
const SPD = { x: 20, w: 62, top: 90, bot: 380, ktsPerPx: 0.55 };
const ALT = { x: 396, w: 70, top: 90, bot: 380, ftPerPx: 3.8 };
const VSI = { x: 472, top: 120, bot: 350 };
const HDG = { y: 432, left: 100, right: 370, pxPerDeg: 3.5 };

export function renderPFD(ctx, s) {
  const f = s.fdm;
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, PFD_W, PFD_H);

  drawADI(ctx, f, s.ap);
  drawSpeedTape(ctx, f, s.ap);
  drawAltTape(ctx, f, s.ap);
  drawVSI(ctx, f);
  drawHeading(ctx, f, s.ap);
  drawFMA(ctx, s);

  // publish last-drawn values for Playwright assertions
  window.__ikarusDebug = window.__ikarusDebug || {};
  window.__ikarusDebug.pfd = {
    cas: f.cas, alt: f.alt, pitch: f.pitch, roll: f.roll, hdg: f.hdg,
  };
}

function drawADI(ctx, f, ap) {
  const { cx, cy, r, pxPerDeg } = ADI;
  ctx.save();
  ctx.beginPath();
  ctx.rect(cx - r, cy - r, 2 * r, 2 * r);
  ctx.clip();

  ctx.translate(cx, cy);
  ctx.rotate(-f.roll * Math.PI / 180);
  ctx.translate(0, f.pitch * pxPerDeg);

  // sky and ground (oversized so they cover during rotation)
  ctx.fillStyle = C.sky;
  ctx.fillRect(-2.5 * r, -2.5 * r - 400, 5 * r, 2.5 * r + 400);
  ctx.fillStyle = C.ground;
  ctx.fillRect(-2.5 * r, 0, 5 * r, 2.5 * r + 400);
  line(ctx, -2.5 * r, 0, 2.5 * r, 0, C.white, 2);

  // pitch ladder
  for (let deg = -30; deg <= 30; deg += 2.5) {
    if (deg === 0) continue;
    const y = -deg * pxPerDeg;
    const major = deg % 10 === 0;
    const half = deg % 5 === 0 && !major;
    const w = major ? 44 : half ? 26 : 13;
    line(ctx, -w, y, w, y, C.white, major ? 2 : 1.5);
    if (major) {
      text(ctx, `${Math.abs(deg)}`, -w - 16, y, { size: 13 });
      text(ctx, `${Math.abs(deg)}`, w + 16, y, { size: 13 });
    }
  }
  ctx.restore();

  // roll scale (fixed) + pointer
  ctx.save();
  ctx.translate(cx, cy);
  for (const deg of [-45, -30, -20, -10, 10, 20, 30, 45]) {
    const a = (-90 + deg) * Math.PI / 180;
    const len = Math.abs(deg) % 30 === 0 ? 14 : 8;
    const x1 = Math.cos(a) * (r - 2), y1 = Math.sin(a) * (r - 2);
    const x2 = Math.cos(a) * (r - 2 + len), y2 = Math.sin(a) * (r - 2 + len);
    line(ctx, x1, y1, x2, y2, C.white, 2);
  }
  poly(ctx, [[0, -r + 2], [-7, -r - 10], [7, -r - 10]], { fill: C.yellow });
  ctx.rotate(-f.roll * Math.PI / 180);
  poly(ctx, [[0, -r + 14], [-7, -r + 26], [7, -r + 26]], { stroke: C.white, width: 2 });
  ctx.restore();

  // fixed aircraft symbol
  ctx.fillStyle = C.bg;
  ctx.strokeStyle = C.yellow;
  ctx.lineWidth = 3;
  for (const side of [-1, 1]) {
    ctx.strokeRect(cx + side * 78 - (side > 0 ? 34 : 0), cy - 4, 34, 8);
  }
  ctx.strokeRect(cx - 4, cy - 4, 8, 8);
}

function drawSpeedTape(ctx, f, ap) {
  const { x, w, top, bot, ktsPerPx } = SPD;
  const cy = (top + bot) / 2;
  ctx.fillStyle = C.gray;
  ctx.fillRect(x, top, w, bot - top);

  ctx.save();
  ctx.beginPath();
  ctx.rect(x, top, w + 14, bot - top);
  ctx.clip();
  const lo = f.cas - (bot - cy) * ktsPerPx;
  const hi = f.cas + (cy - top) * ktsPerPx;
  for (let k = Math.ceil(lo / 10) * 10; k <= hi; k += 10) {
    if (k < 30) continue;
    const y = cy - (k - f.cas) / ktsPerPx;
    line(ctx, x + w - 10, y, x + w, y, C.white, 2);
    if (k % 20 === 0) text(ctx, `${k}`, x + w - 14, y, { size: 15, align: "right" });
  }
  // target speed marker (cyan triangle)
  const ty = cy - (ap.spd - f.cas) / ktsPerPx;
  poly(ctx, [[x + w, ty], [x + w + 10, ty - 7], [x + w + 10, ty + 7]], { fill: C.cyan });
  ctx.restore();

  // reference line
  line(ctx, x, cy, x + w + 6, cy, C.yellow, 3);
  text(ctx, `${Math.round(f.mach * 1000) / 1000}`.replace("0.", "."), x + w / 2, bot + 18,
       { size: 15, color: C.green });
  // off-scale target speed
  if (Math.abs(ap.spd - f.cas) > (cy - top) * ktsPerPx) {
    text(ctx, `${ap.spd}`, x + w / 2, top - 12, { size: 14, color: C.cyan });
  }
}

function drawAltTape(ctx, f, ap) {
  const { x, w, top, bot, ftPerPx } = ALT;
  const cy = (top + bot) / 2;
  ctx.fillStyle = C.gray;
  ctx.fillRect(x, top, w, bot - top);

  ctx.save();
  ctx.beginPath();
  ctx.rect(x - 14, top, w + 14, bot - top);
  ctx.clip();
  const lo = f.alt - (bot - cy) * ftPerPx;
  const hi = f.alt + (cy - top) * ftPerPx;
  for (let ft = Math.ceil(lo / 100) * 100; ft <= hi; ft += 100) {
    const y = cy - (ft - f.alt) / ftPerPx;
    line(ctx, x, y, x + 10, y, C.white, 2);
    if (ft % 500 === 0) {
      text(ctx, `${ft / 100}`, x + 16, y, { size: 15, align: "left" });
    }
  }
  // selected altitude (cyan)
  const ty = cy - (ap.alt - f.alt) / ftPerPx;
  poly(ctx, [[x, ty - 9], [x - 10, ty - 9], [x - 10, ty + 9], [x, ty + 9]],
       { stroke: C.cyan, width: 2, close: false });
  ctx.restore();

  // current altitude box
  const boxY = cy;
  ctx.fillStyle = C.bg;
  ctx.fillRect(x + 4, boxY - 14, w - 4, 28);
  ctx.strokeStyle = C.yellow;
  ctx.lineWidth = 2;
  ctx.strokeRect(x + 4, boxY - 14, w - 4, 28);
  text(ctx, `${Math.round(f.alt / 20) * 20}`, x + w - 4, boxY,
       { size: 17, color: C.green, align: "right", bold: true });
  if (Math.abs(ap.alt - f.alt) > (cy - top) * ftPerPx) {
    text(ctx, `${ap.alt}`, x + w / 2, top - 12, { size: 14, color: C.cyan });
  }
}

function drawVSI(ctx, f) {
  const { x, top, bot } = VSI;
  const cy = (top + bot) / 2;
  ctx.fillStyle = C.gray;
  ctx.fillRect(x - 4, top, 26, bot - top);
  for (const v of [-6, -4, -2, -1, 1, 2, 4, 6]) {
    const y = cy - vsToPx(v * 1000);
    line(ctx, x - 4, y, x + 2, y, C.white, 2);
    if (Math.abs(v) !== 1) text(ctx, `${Math.abs(v)}`, x + 10, y, { size: 11 });
  }
  const vy = cy - vsToPx(f.vs);
  line(ctx, x - 4, vy, x + 20, cy - vsToPx(f.vs) * 0.4, C.green, 3);
  if (Math.abs(f.vs) > 200) {
    const label = `${Math.abs(Math.round(f.vs / 100))}`.padStart(2, "0");
    text(ctx, label, x + 10, vy + (f.vs > 0 ? -14 : 14), { size: 13, color: C.green });
  }

  function vsToPx(vs) {
    // nonlinear scale like the real VSI: compress beyond 2000 fpm
    const v = Math.max(-6000, Math.min(6000, vs));
    const sign = Math.sign(v);
    const a = Math.abs(v);
    const px = a <= 2000 ? (a / 2000) * 55 : 55 + ((a - 2000) / 4000) * 45;
    return sign * px;
  }
}

function drawHeading(ctx, f, ap) {
  const { y, left, right, pxPerDeg } = HDG;
  const cx = (left + right) / 2;
  ctx.fillStyle = C.gray;
  ctx.fillRect(left, y, right - left, 36);
  ctx.save();
  ctx.beginPath();
  ctx.rect(left, y - 12, right - left, 50);
  ctx.clip();
  const span = (right - left) / 2 / pxPerDeg;
  for (let d = -span; d <= span; d += 5) {
    const hdg = (Math.round((f.hdg + d) / 5) * 5 + 360) % 360;
    const x = cx + (((hdg - f.hdg + 540) % 360) - 180) * pxPerDeg;
    if (x < left || x > right) continue;
    const major = hdg % 10 === 0;
    line(ctx, x, y, x, y + (major ? 10 : 6), C.white, major ? 2 : 1.5);
    if (hdg % 10 === 0) {
      text(ctx, `${hdg / 10}`, x, y + 24, { size: 13 });
    }
  }
  // selected heading bug
  const bx = cx + (((ap.hdg - f.hdg + 540) % 360) - 180) * pxPerDeg;
  poly(ctx, [[bx, y], [bx - 7, y - 10], [bx + 7, y - 10]], { fill: C.cyan });
  ctx.restore();
  // lubber line
  line(ctx, cx, y - 6, cx, y + 12, C.yellow, 3);
}

function drawFMA(ctx, s) {
  // M1 placeholder FMA: A/THR | vertical | lateral | - | AP status
  const y = 26;
  const cols = [62, 170, 278, 386, 462];
  line(ctx, 10, 48, 490, 48, C.gray, 1);
  for (const x of [116, 224, 332, 420]) line(ctx, x, 8, x, 44, C.gray, 1);
  if (s.ap.athr) text(ctx, "SPEED", cols[0], y, { size: 15, color: C.green });
  if (s.ap.ap) {
    text(ctx, "V/S", cols[1], y, { size: 15, color: C.green });
    text(ctx, "HDG", cols[2], y, { size: 15, color: C.green });
    text(ctx, "AP1", cols[4], y - 10, { size: 13, color: C.white });
  }
  if (s.ap.athr) text(ctx, "A/THR", cols[4], y + 26, { size: 13, color: C.white });
  if (s.sim.paused) text(ctx, "PAUSE", 250, 70, { size: 18, color: C.amber, bold: true });
  if (s.sim.accel > 1) text(ctx, `${s.sim.accel}x`, 250, 90, { size: 14, color: C.amber });
}
