"""Central configuration: loop rates, paths, and controller gains.

Every tunable number in the simulation lives here so that gain tuning
against the stock A320 flight model never requires hunting through
system code.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
FRONTEND_DIR = REPO_ROOT / "frontend"
NAVDATA_DB = DATA_DIR / "navdata" / "navdata.db"
PROCEDURES_DIR = DATA_DIR / "navdata" / "procedures"

# --- Loop rates -------------------------------------------------------------
FDM_HZ = 120          # JSBSim step + FBW inner loop
SYSTEMS_HZ = 30       # aircraft systems + autoflight outer loops
FDM_STEPS_PER_SYSTEMS_TICK = FDM_HZ // SYSTEMS_HZ
FWC_HZ = 10           # ECAM / flight warning computer
SNAPSHOT_HZ = 15      # WebSocket state broadcast

# Wall-clock pacing: if the sim falls further behind than this, drop the
# debt instead of trying to catch up (prevents death spirals).
MAX_TIME_DEBT_S = 0.5
TIME_ACCEL_STEPS = (1, 2, 4)

# --- Aircraft ---------------------------------------------------------------
AIRCRAFT_MODEL = "A320"
N_ENGINES = 2

# --- Default situations -----------------------------------------------------
# Frankfurt (EDDF) area defaults until a flight plan overrides them.
DEFAULT_LAT_DEG = 50.0333
DEFAULT_LON_DEG = 8.5706
CRUISE_ALT_FT = 33000.0
CRUISE_CAS_KTS = 280.0
