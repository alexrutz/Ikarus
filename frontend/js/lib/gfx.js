// Canvas helpers shared by all displays. A320 display palette.

export const C = {
  bg: "#000000",
  gray: "#4c4f55",      // display background panels
  white: "#ffffff",
  green: "#00d000",
  cyan: "#00e0e0",
  magenta: "#ff00ff",
  amber: "#e8a000",
  red: "#ff2a2a",
  sky: "#0069aa",
  ground: "#8b4513",
  yellow: "#ffff00",
};

export function text(ctx, str, x, y, { size = 16, color = C.white, align = "center",
                                        baseline = "middle", font = "monospace", bold = false } = {}) {
  ctx.fillStyle = color;
  ctx.font = `${bold ? "bold " : ""}${size}px ${font}`;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  ctx.fillText(str, x, y);
}

export function line(ctx, x1, y1, x2, y2, color = C.white, width = 2) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

export function poly(ctx, pts, { fill = null, stroke = null, width = 2, close = true } = {}) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  if (close) ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width; ctx.stroke(); }
}

// Setup a canvas for crisp rendering at devicePixelRatio; returns ctx
// scaled so drawing code works in CSS-pixel units of (w, h).
export function setupCanvas(canvas, w, h) {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}
