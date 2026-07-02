// Failure injection panel (instructor station).

const CATALOG = [
  ["ENG1_FLAMEOUT", "ENG 1 FLAMEOUT"],
  ["ENG2_FLAMEOUT", "ENG 2 FLAMEOUT"],
  ["ELEC_GEN1", "GEN 1 FAULT"],
  ["ELEC_GEN2", "GEN 2 FAULT"],
  ["HYD_G_LEAK", "GREEN HYD LEAK"],
  ["HYD_B_LEAK", "BLUE HYD LEAK"],
  ["HYD_Y_LEAK", "YELLOW HYD LEAK"],
  ["ELAC1", "ELAC 1 FAULT"],
  ["ELAC2", "ELAC 2 FAULT"],
  ["SEC1", "SEC 1 FAULT"],
  ["SEC2", "SEC 2 FAULT"],
  ["SEC3", "SEC 3 FAULT"],
  ["BLEED1", "BLEED 1 FAULT"],
  ["BLEED2", "BLEED 2 FAULT"],
  ["PACK1", "PACK 1 FAULT"],
  ["PACK2", "PACK 2 FAULT"],
];

export function buildFailures(container, link) {
  container.innerHTML = "";
  const box = document.createElement("fieldset");
  box.className = "ovhd-section";
  box.innerHTML = "<legend>FAILURE INJECTION</legend>";
  const buttons = new Map();
  for (const [id, label] of CATALOG) {
    const b = document.createElement("button");
    b.className = "ovhd-btn fail";
    b.innerHTML = `<span>${label}</span><em>—</em>`;
    b.onclick = () => {
      const active = b.classList.contains("on");
      link.cmd(active ? "failure.clear" : "failure.set", id);
    };
    box.appendChild(b);
    buttons.set(id, b);
  }
  const clear = document.createElement("button");
  clear.className = "ovhd-btn";
  clear.innerHTML = "<span>CLEAR ALL</span><em></em>";
  clear.onclick = () => link.cmd("failure.clear_all");
  box.appendChild(clear);
  container.appendChild(box);

  return {
    update(snap) {
      const active = new Set(snap.failures || []);
      for (const [id, b] of buttons) {
        const on = active.has(id);
        b.classList.toggle("on", on);
        b.querySelector("em").textContent = on ? "ACTIVE" : "—";
      }
    },
  };
}
