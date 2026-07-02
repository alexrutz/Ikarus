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

## Features

- **Flight deck**: PFD (attitude, tapes, FMA, FD bars, ILS scales), ND
  (ROSE/ARC, route, ToD, VOR needles), E/WD (engine gauges, ECAM
  alerts/memos), SD (ELEC/HYD/FUEL/BLEED/PRESS/APU/ENG/F-CTL/CRUISE
  pages with auto page call), FCU, MCDU, overhead panel.
- **Autoflight**: FBW normal law with protections (bank/pitch/alpha/
  g-load/overspeed) and alternate/direct degradation; FCU selected +
  managed modes (HDG, NAV, ALT*/ALT, V/S, OP CLB/DES, managed CLB/DES,
  LOC, G/S with APPR); autothrust with thrust-lever detents.
- **FMS**: MCDU route entry (INIT, DEPART/ARRIVE, F-PLN, DIR TO,
  RAD NAV, PERF, PROG), SIDs/STARs/ILS approaches (sample data for
  EDDF, EDDM, KSFO), LNAV with turn anticipation, simplified VNAV
  profile with constraints and ToD.
- **Systems**: electrical buses with source priority, G/B/Y hydraulics
  with PTU and RAT, 5-tank fuel system with crossfeed, bleed air,
  pressurization, APU, full engine start sequencing — all with real
  dependency modeling (no bleed, no start; no AC, no fuel pumps...).
- **ECAM/FWC**: ~20 sensed alerts with master warning/caution, memos,
  CLR/RCL, flight phases.
- **Failure injection**: engines, generators, hydraulic leaks,
  flight-control computers, bleed/packs — from the FAIL panel or the
  command API.
- **Cold & dark**: full start flow (battery → APU → bleed → engines).

Try the scripted showcase (headless, fast-time):

```bash
python scripts/fly_demo.py
```

Full worldwide navdata (optional; the committed seed covers large
airports + EU/US-west navaids):

```bash
python scripts/fetch_navdata.py
```

## Status / roadmap

- [x] M0 — JSBSim A320 adapter, property surface verified, smoke tests
- [x] M1 — sim loop, WebSocket server, live PFD, provisional AP holds
- [x] M2 — FBW normal law + protections, FCU, mode logic (FMA), A/THR detents
- [x] M3 — FMS flight plans, MCDU, navdata (OurAirports), ND, ILS approach
- [x] M4 — electrical/hydraulic/fuel/bleed/pressurization/APU systems, ECAM
- [x] M5 — failure injection, alternate/direct law, Playwright display tests

Deferred (contributions welcome): airways + FAA CIFP procedure import,
SRS/GA modes, fire systems, joystick input, weather beyond JSBSim winds.
