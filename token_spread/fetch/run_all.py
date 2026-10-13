"""Run every fetcher. A failing source keeps its previous CSV (and says so),
so one broken page never blocks the daily snapshot."""
from __future__ import annotations

import sys
import traceback

import fetch_inferencex
import fetch_openrouter
import fetch_power
import fetch_silicondata

# order matters: silicondata merges the GPU costs written by inferencex
STEPS = [("openrouter", fetch_openrouter), ("inferencex", fetch_inferencex),
         ("silicondata", fetch_silicondata), ("power", fetch_power)]


def main() -> int:
    failed = []
    for name, mod in STEPS:
        print(f"--- {name}")
        try:
            mod.main()
        except Exception:
            traceback.print_exc()
            print(f"WARNING: {name} fetch failed; keeping previous data file")
            failed.append(name)
    if failed:
        print(f"Failed sources: {', '.join(failed)}")
    # only fail the run if every source failed
    return 1 if len(failed) == len(STEPS) else 0


if __name__ == "__main__":
    sys.exit(main())
