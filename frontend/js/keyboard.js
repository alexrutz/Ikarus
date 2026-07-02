// Keyboard -> sim commands. Stick keys send pulses; the backend decays them.

export function bindKeyboard(link) {
  const pulse = { ArrowUp: ["ctl.pitch", -0.15], ArrowDown: ["ctl.pitch", 0.15],
                  ArrowLeft: ["ctl.roll", -0.2], ArrowRight: ["ctl.roll", 0.2],
                  ",": ["ctl.rudder", -0.2], ".": ["ctl.rudder", 0.2] };

  const detents = { 1: "IDLE", 2: "CLB", 3: "FLX", 4: "TOGA" };

  let flaps = 0, gear = true, spdbrk = 0, paused = false, accel = 1;
  let thrustMan = 0.6;

  // sync local toggles from server snapshots
  link.syncFromSnap = (s) => {
    flaps = s.ctl.flaps; gear = s.ctl.gear; spdbrk = s.ctl.spdbrk;
    paused = s.sim.paused; accel = s.sim.accel;
    if (s.ctl.detent === "MAN") thrustMan = s.ctl.thrust_man;
  };

  window.addEventListener("keydown", (ev) => {
    if (ev.target.tagName === "INPUT") return;
    const p = pulse[ev.key];
    if (p) { link.cmd(p[0], p[1]); ev.preventDefault(); return; }
    if (detents[ev.key]) { link.cmd("ctl.thrust.detent", detents[ev.key]); return; }
    switch (ev.key) {
      case "=": case "+":
        thrustMan = Math.min(1, thrustMan + 0.05);
        link.cmd("ctl.thrust.manual", thrustMan);
        break;
      case "-":
        thrustMan = Math.max(0, thrustMan - 0.05);
        link.cmd("ctl.thrust.manual", thrustMan);
        break;
      case "f": flaps = Math.min(4, flaps + 1); link.cmd("ctl.flaps", flaps); break;
      case "v": flaps = Math.max(0, flaps - 1); link.cmd("ctl.flaps", flaps); break;
      case "g": gear = !gear; link.cmd("ctl.gear", gear); break;
      case "b": spdbrk = spdbrk > 0 ? 0 : 1; link.cmd("ctl.speedbrake", spdbrk); break;
      case " ": link.cmd("fcu.ap1.toggle", false); ev.preventDefault(); break;
      case "p": paused = !paused; link.cmd("sim.pause", paused); break;
      case "[": accel = Math.max(1, accel / 2); link.cmd("sim.accel", accel); break;
      case "]": accel = Math.min(4, accel * 2); link.cmd("sim.accel", accel); break;
    }
  });
}
