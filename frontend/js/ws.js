// WebSocket client: state store with dead-reckoning between snapshots.
//
// Snapshots arrive at ~15 Hz and include body/path rates; view() returns
// the last snapshot with attitude/altitude extrapolated to "now" so the
// render loop can draw smoothly at display refresh rate.

const RAD_TO_DEG = 57.29577951308232;
const MAX_EXTRAP_S = 0.35;

export class SimLink {
  constructor(url) {
    this.url = url;
    this.snap = null;
    this.snapAt = 0;
    this.connected = false;
    this.onstatus = () => {};
    this._connect();
  }

  _connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => { this.connected = true; this.onstatus(); };
    this.ws.onclose = () => {
      this.connected = false;
      this.onstatus();
      setTimeout(() => this._connect(), 1000);
    };
    this.ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.t === "snap") {
        this.snap = msg;
        this.snapAt = performance.now();
      } else if (msg.t === "err") {
        console.warn("sim error:", msg.msg);
      }
    };
  }

  cmd(name, value = null) {
    if (this.connected) {
      this.ws.send(JSON.stringify({ t: "cmd", name, value }));
    }
  }

  // Latest state, dead-reckoned to the current frame time.
  view() {
    if (!this.snap) return null;
    const s = this.snap;
    let dt = (performance.now() - this.snapAt) / 1000;
    if (s.sim.paused) dt = 0;
    dt = Math.min(dt, MAX_EXTRAP_S) * s.sim.accel;
    const f = s.fdm;
    return {
      ...s,
      fdm: {
        ...f,
        pitch: f.pitch + f.q * RAD_TO_DEG * dt,
        roll: f.roll + f.p * RAD_TO_DEG * dt,
        hdg: (f.hdg + f.r * RAD_TO_DEG * dt + 360) % 360,
        alt: f.alt + (f.vs / 60) * dt,
      },
    };
  }
}
