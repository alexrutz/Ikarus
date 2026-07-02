#!/usr/bin/env python3
"""Download the full OurAirports dataset and rebuild the navdata SQLite DB.

Without this, the simulator uses the committed seed extract (large
airports worldwide + navaids for Europe/US-west), which is enough for
the sample procedures.
"""

import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ikarus import config                    # noqa: E402
from ikarus.nav import ingest                # noqa: E402

BASE = "https://davidmegginson.github.io/ourairports-data"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for name in ("airports", "runways", "navaids"):
            url = f"{BASE}/{name}.csv"
            print(f"downloading {url} ...")
            urllib.request.urlretrieve(url, tmp_path / f"{name}.csv")
        print("building", config.NAVDATA_DB)
        ingest.build_db(tmp_path, config.NAVDATA_DB)
    print("done")


if __name__ == "__main__":
    main()
