// MCDU panel: dumb terminal for the server-side page machine.
// Renders 14 lines of [col, text, color] segments and a keypad.

const COLORS = { w: "#e8e8e8", g: "#00d000", c: "#00e0e0",
                 a: "#e8a000", m: "#ff00ff", y: "#ffff00" };

const KEY_ROWS = [
  ["INIT", "FPLN", "RADNAV", "PERF", "PROG", "DIR"],
  ["DEPART", "ARRIVE", "UP", "DOWN", "CLR", "OVFY"],
  ["A", "B", "C", "D", "E", "F", "G"],
  ["H", "I", "J", "K", "L", "M", "N"],
  ["O", "P", "Q", "R", "S", "T", "U"],
  ["V", "W", "X", "Y", "Z", "/", "-"],
  ["1", "2", "3", "4", "5", "6", "7"],
  ["8", "9", "0", ".", "+", " ", ""],
];

export function buildMcdu(container, link) {
  container.innerHTML = "";
  const screen = document.createElement("div");
  screen.className = "mcdu-screen";
  const rows = [];
  for (let i = 0; i < 14; i++) {
    const row = document.createElement("div");
    row.className = "mcdu-row";
    // LSK buttons on label rows (1,3,5,7,9,11 -> LSK1..6)
    screen.appendChild(row);
    rows.push(row);
  }
  container.appendChild(screen);

  // LSK columns (left/right of the screen)
  for (const side of ["L", "R"]) {
    const col = document.createElement("div");
    col.className = `mcdu-lsk mcdu-lsk-${side.toLowerCase()}`;
    for (let n = 1; n <= 6; n++) {
      const b = document.createElement("button");
      b.textContent = "—";
      b.title = `LSK${n}${side}`;
      b.onclick = () => link.cmd("mcdu.key", `LSK${n}${side}`);
      col.appendChild(b);
    }
    container.appendChild(col);
  }

  const pad = document.createElement("div");
  pad.className = "mcdu-pad";
  for (const keyRow of KEY_ROWS) {
    const rowEl = document.createElement("div");
    for (const k of keyRow) {
      const b = document.createElement("button");
      b.textContent = k || "";
      b.disabled = !k;
      if (k) b.onclick = () => link.cmd("mcdu.key", k === " " ? " " : k);
      rowEl.appendChild(b);
    }
    pad.appendChild(rowEl);
  }
  container.appendChild(pad);

  return {
    update(fmsSnap) {
      const lines = fmsSnap.mcdu.lines || [];
      for (let i = 0; i < 14; i++) {
        const row = rows[i];
        row.innerHTML = "";
        const segs = lines[i] || [];
        // build a 24-char line from positioned segments
        const chars = new Array(24).fill(null);
        for (const [col, txt, color] of segs) {
          for (let j = 0; j < txt.length && col + j < 24; j++) {
            chars[col + j] = [txt[j], color];
          }
        }
        let span = null, spanColor = null;
        for (let j = 0; j < 24; j++) {
          const cell = chars[j] || [" ", "w"];
          if (cell[1] !== spanColor) {
            span = document.createElement("span");
            spanColor = cell[1];
            span.style.color = COLORS[spanColor] || COLORS.w;
            row.appendChild(span);
          }
          span.textContent += cell[0];
        }
      }
    },
  };
}
