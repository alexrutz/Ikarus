# Ikarus

A JSBSim-based **instrument-only flight simulator** for commercial aircraft
with full system depth. No 3D scenery — the simulator is the flight deck:
PFD, ND, ECAM, FCU, MCDU and overhead panel of an A320-family aircraft,
rendered in the browser and driven by a Python simulation backend.

## Quick start

```bash
pip install -e .[dev]
python -m ikarus                 # http://localhost:8080
python -m ikarus --situation runway   # start on the runway instead of cruise
```

Open the page, and you are looking at a live PFD. Fly with the autopilot
strip (SPD/HDG/ALT/V-S), or hand-fly with the keyboard:

| Key | Action |
|-----|--------|
| arrows | sidestick (attitude command) |
| `-` / `=` | thrust |
| `f` / `v` | flaps extend / retract |
| `g` | gear |
| `b` | speedbrake |
| `space` | autopilot off |
| `p` | pause |
| `[` / `]` | time acceleration |

## Architecture

- **Flight dynamics**: JSBSim (the bundled A320 model) stepped at 120 Hz.
- **FBW & autoflight**: Python — an attitude-command inner loop at FDM
  rate, outer loops (autopilot/autothrust) and aircraft systems at 30 Hz.
- **Cockpit**: build-free vanilla JS + Canvas, fed ~15 Hz state snapshots
  over WebSocket with client-side dead reckoning for smooth rendering.
- **Everything testable headlessly**: `pytest` runs scripted flights in
  fast time (no server, no browser).

```bash
python -m pytest
```

## Status / roadmap

- [x] M0 — JSBSim A320 adapter, property surface verified, smoke tests
- [x] M1 — sim loop, WebSocket server, live PFD, provisional AP holds
- [x] M2 — FBW normal law + protections, FCU, mode logic (FMA), A/THR detents
- [x] M3 — FMS flight plans, MCDU, navdata (OurAirports), ND, ILS approach
- [x] M4 — electrical/hydraulic/fuel/bleed/pressurization/APU systems, ECAM
- [ ] M5 — failure injection, alternate/direct law, Playwright display tests
