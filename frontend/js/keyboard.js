// Keyboard -> sim commands. Stick keys send pulses; the backend decays them.

export function bindKeyboard(link) {
  let thrust = 0.6;

  const pulse = { ArrowUp: ["ctl.pitch", -0.15], ArrowDown: ["ctl.pitch", 0.15],
                  ArrowLeft: ["ctl.roll", -0.2], ArrowRight: ["ctl.roll", 0.2],
                  ",": ["ctl.rudder", -0.2], ".": ["ctl.rudder", 0.2] };

  let flaps = 0, gear = true, spdbrk = 0, paused = false, accel = 1;

  // sync local toggles from server snapshots
  link.syncFromSnap = (s) => {
    flaps = s.ctl.flaps; gear = s.ctl.gear; spdbrk = s.ctl.spdbrk;
    thrust = s.ctl.thrust; paused = s.sim.paused; accel = s.sim.accel;
  };

  window.addEventListener("keydown", (ev) => {
    if (ev.target.tagName === "INPUT") return;
    const p = pulse[ev.key];
    if (p) { link.cmd(p[0], p[1]); ev.preventDefault(); return; }
    switch (ev.key) {
      case "=": case "+": thrust = Math.min(1, thrust + 0.05); link.cmd("ctl.thrust", thrust); break;
      case "-": thrust = Math.max(0, thrust - 0.05); link.cmd("ctl.thrust", thrust); break;
      case "f": flaps = Math.min(4, flaps + 1); link.cmd("ctl.flaps", flaps); break;
      case "v": flaps = Math.max(0, flaps - 1); link.cmd("ctl.flaps", flaps); break;
      case "g": gear = !gear; link.cmd("ctl.gear", gear); break;
      case "b": spdbrk = spdbrk > 0 ? 0 : 1; link.cmd("ctl.speedbrake", spdbrk); break;
      case " ": link.cmd("ap.toggle", false); ev.preventDefault(); break;
      case "p": paused = !paused; link.cmd("sim.pause", paused); break;
      case "[": accel = Math.max(1, accel / 2); link.cmd("sim.accel", accel); break;
      case "]": accel = Math.min(4, accel * 2); link.cmd("sim.accel", accel); break;
    }
  });
}
