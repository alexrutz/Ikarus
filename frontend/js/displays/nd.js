// Navigation Display: ROSE / ARC modes, route, waypoints, ToD, VOR bearing.
// Design space 500x500. Heading-up. Range selectable via EFIS control.

import { C, text, line, poly } from "../lib/gfx.js";

export const ND_W = 500;
export const ND_H = 500;

// screen position of the aircraft symbol per mode
const CENTER = { rose: [250, 260], arc: [250, 420] };

export function renderND(ctx, s, efis) {
  const f = s.fdm;
  const mode = efis.mode;      // "rose" | "arc"
  const range = efis.range;    // nm, full-scale radius (rose: half)
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, ND_W, ND_H);

  const [cx, cy] = CENTER[mode] || CENTER.rose;
  const radiusPx = mode === "arc" ? 330 : 175;
  const nmToPx = radiusPx / range;
  const hdg = f.hdg;

  // project lat/lon to screen (heading-up, equirectangular around aircraft)
  const cosLat = Math.cos(f.lat * Math.PI / 180);
  const toScreen = (lat, lon) => {
    const dxNm = (lon - f.lon) * 60 * cosLat;
    const dyNm = (lat - f.lat) * 60;
    const a = -hdg * Math.PI / 180;
    const xr = dxNm * Math.cos(a) - dyNm * Math.sin(a);
    const yr = dxNm * Math.sin(a) + dyNm * Math.cos(a);
    return [cx + xr * nmToPx, cy - yr * nmToPx];
  };

  drawCompass(ctx, cx, cy, radiusPx, hdg, mode, s);
  drawRoute(ctx, s, toScreen, cx, cy, nmToPx);
  drawVorNeedles(ctx, s, cx, cy, radiusPx, hdg);
  drawAircraft(ctx, cx, cy);
  drawTexts(ctx, s, range);

  window.__ikarusDebug = window.__ikarusDebug || {};
  window.__ikarusDebug.nd = { range, mode, legs: s.fms.legs.length,
                              xtk: s.fms.xtk };
}

function drawCompass(ctx, cx, cy, r, hdg, mode, s) {
  ctx.save();
  ctx.beginPath();
  if (mode === "arc") {
    ctx.rect(0, 0, ND_W, cy + 20);
  } else {
    ctx.rect(0, 0, ND_W, ND_H);
  }
  ctx.clip();

  ctx.strokeStyle = C.white;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, 2 * Math.PI);
  ctx.stroke();

  for (let d = 0; d < 360; d += 5) {
    const a = (d - hdg - 90) * Math.PI / 180;
    const major = d % 10 === 0;
    const r1 = r, r2 = r + (major ? 12 : 7);
    line(ctx, cx + Math.cos(a) * r1, cy + Math.sin(a) * r1,
         cx + Math.cos(a) * r2, cy + Math.sin(a) * r2, C.white, 1.5);
    if (d % 30 === 0) {
      const rt = r + 26;
      text(ctx, `${d / 10}`, cx + Math.cos(a) * rt, cy + Math.sin(a) * rt,
           { size: 14 });
    }
  }
  // half-range ring (dashed)
  ctx.setLineDash([6, 6]);
  ctx.strokeStyle = C.white;
  ctx.beginPath();
  ctx.arc(cx, cy, r / 2, 0, 2 * Math.PI);
  ctx.stroke();
  ctx.setLineDash([]);

  // track diamond on the rose
  const trkA = (s.fdm.track - hdg - 90) * Math.PI / 180;
  poly(ctx, [
    [cx + Math.cos(trkA) * (r - 8), cy + Math.sin(trkA) * (r - 8)],
    [cx + Math.cos(trkA) * r + 6 * Math.sin(trkA), cy + Math.sin(trkA) * r - 6 * Math.cos(trkA)],
    [cx + Math.cos(trkA) * (r + 8), cy + Math.sin(trkA) * (r + 8)],
    [cx + Math.cos(trkA) * r - 6 * Math.sin(trkA), cy + Math.sin(trkA) * r + 6 * Math.cos(trkA)],
  ], { stroke: C.green, width: 2 });
  ctx.restore();

  // lubber line
  line(ctx, cx, cy - r - 18, cx, cy - r + 12, C.yellow, 3);
}

function drawRoute(ctx, s, toScreen, cx, cy, nmToPx) {
  const legs = s.fms.legs;
  if (!legs.length) return;
  const active = s.fms.active_idx;

  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, ND_W, ND_H);
  ctx.clip();

  // route line
  for (let i = 1; i < legs.length; i++) {
    const [x1, y1] = toScreen(legs[i - 1].lat, legs[i - 1].lon);
    const [x2, y2] = toScreen(legs[i].lat, legs[i].lon);
    const isActive = i === active;
    ctx.setLineDash(i < active ? [4, 6] : []);
    line(ctx, x1, y1, x2, y2, isActive ? C.magenta : C.green, 2);
  }
  ctx.setLineDash([]);

  // waypoints
  for (let i = 0; i < legs.length; i++) {
    const [x, y] = toScreen(legs[i].lat, legs[i].lon);
    if (x < -20 || x > ND_W + 20 || y < -20 || y > ND_H + 20) continue;
    const color = i === active ? C.white : C.green;
    poly(ctx, [[x, y - 5], [x + 5, y], [x, y + 5], [x - 5, y]],
         { stroke: color, width: 2 });
    text(ctx, legs[i].id, x + 9, y - 9,
         { size: 12, color, align: "left" });
  }

  // top-of-descent arrow (along the route, tod nm ahead)
  if (s.fms.tod > 0 && active >= 0 && active < legs.length) {
    const todPt = alongRoutePoint(s, s.fms.tod);
    if (todPt) {
      const [x, y] = toScreen(todPt[0], todPt[1]);
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, 2 * Math.PI);
      ctx.strokeStyle = C.white;
      ctx.lineWidth = 2;
      ctx.stroke();
      text(ctx, "T/D", x + 8, y + 8, { size: 11, color: C.white, align: "left" });
    }
  }
  ctx.restore();
}

// walk the remaining route to find the point `dist` nm ahead
function alongRoutePoint(s, dist) {
  const f = s.fdm;
  const legs = s.fms.legs;
  let prev = [f.lat, f.lon];
  let remaining = dist;
  for (let i = s.fms.active_idx; i >= 0 && i < legs.length; i++) {
    const next = [legs[i].lat, legs[i].lon];
    const d = gcDistNm(prev, next);
    if (remaining <= d) {
      const frac = d > 0 ? remaining / d : 0;
      return [prev[0] + (next[0] - prev[0]) * frac,
              prev[1] + (next[1] - prev[1]) * frac];
    }
    remaining -= d;
    prev = next;
  }
  return null;
}

function gcDistNm(a, b) {
  const dlat = (b[0] - a[0]) * 60;
  const dlon = (b[1] - a[1]) * 60 * Math.cos(a[0] * Math.PI / 180);
  return Math.hypot(dlat, dlon);
}

function drawVorNeedles(ctx, s, cx, cy, r, hdg) {
  // rose is true-heading-up; navaid bearings arrive magnetic
  const magvar = s.fdm.magvar || 0;
  for (const [nav, color] of [[s.radio.nav1, C.white], [s.radio.nav2, C.cyan]]) {
    if (!nav || !nav.ok) continue;
    const a = (nav.brg + magvar - hdg - 90) * Math.PI / 180;
    // single-line bearing pointer, head and tail
    line(ctx, cx + Math.cos(a) * (r * 0.55), cy + Math.sin(a) * (r * 0.55),
         cx + Math.cos(a) * (r * 0.85), cy + Math.sin(a) * (r * 0.85),
         color, 2.5);
    line(ctx, cx - Math.cos(a) * (r * 0.55), cy - Math.sin(a) * (r * 0.55),
         cx - Math.cos(a) * (r * 0.85), cy - Math.sin(a) * (r * 0.85),
         color, 1.5);
  }
}

function drawAircraft(ctx, cx, cy) {
  poly(ctx, [[cx, cy - 14], [cx - 9, cy + 10], [cx, cy + 4], [cx + 9, cy + 10]],
       { fill: C.yellow });
}

function drawTexts(ctx, s, range) {
  const f = s.fdm;
  text(ctx, `GS ${Math.round(f.gs)}`, 12, 16, { size: 14, color: C.green, align: "left" });
  text(ctx, `TAS ${Math.round(f.tas)}`, 12, 34, { size: 13, color: C.green, align: "left" });
  text(ctx, `RNG ${range}`, 12, ND_H - 14, { size: 12, color: C.cyan, align: "left" });

  // active waypoint info (top right)
  const legs = s.fms.legs;
  const a = s.fms.active_idx;
  if (a >= 0 && a < legs.length) {
    text(ctx, legs[a].id, ND_W - 12, 16, { size: 14, color: C.white, align: "right" });
    text(ctx, `${s.fms.dtg.toFixed(1)} NM`, ND_W - 12, 34,
         { size: 13, color: C.green, align: "right" });
    text(ctx, `XTK ${s.fms.xtk > 0 ? "R" : "L"}${Math.abs(s.fms.xtk).toFixed(2)}`,
         ND_W - 12, 52, { size: 12, color: C.green, align: "right" });
  }
  // ILS status (bottom right)
  if (s.radio.ils.ok) {
    text(ctx, `${s.radio.ils.id} CRS ${s.radio.ils.crs}`, ND_W - 12, ND_H - 32,
         { size: 12, color: C.magenta, align: "right" });
    text(ctx, `${s.radio.ils.dme} NM`, ND_W - 12, ND_H - 14,
         { size: 12, color: C.magenta, align: "right" });
  }
}
