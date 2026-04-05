# services/crawler/runner.py
"""
Simple focused crawler runner:
- expects seeds/<org>.txt with one URL per line (ignores blank lines and comments)
- uses services.crawler.crawler_tor.fetch_and_save to fetch via Tor and save results
- enforces per-org max_pages per run and per-host politeness (delegated to fetch function)
"""
import os
import time
from pathlib import Path
from typing import List
from services.crawler.crawler_tor import fetch_and_save

SEEDS_DIR = Path("seeds")
PER_ORG_MAX = int(os.getenv("RUNNER_PER_ORG_MAX", "20"))
DELAY_BETWEEN_ORGS = float(os.getenv("RUNNER_DELAY_BETWEEN_ORGS", "2.0"))
ROTATE_CIRCUIT = os.getenv("RUNNER_ROTATE_CIRCUIT", "false").lower() in ("1","true","yes")

def load_seeds_for_org(org: str) -> List[str]:
    f = SEEDS_DIR / f"{org}.txt"
    if not f.exists():
        return []
    lines = [ln.strip() for ln in f.read_text().splitlines()]
    seeds = [ln for ln in lines if ln and not ln.startswith("#")]
    return seeds

def run_all(orgs: List[str] = None):
    if not SEEDS_DIR.exists():
        print("No seeds/ directory found. Create seeds/<org>.txt files first.")
        return
    org_files = [p.stem for p in SEEDS_DIR.glob("*.txt")]
    if orgs:
        org_list = [o for o in orgs if (SEEDS_DIR / f"{o}.txt").exists()]
    else:
        org_list = org_files
    print("Found org seeds:", org_list)
    for org in org_list:
        seeds = load_seeds_for_org(org)[:PER_ORG_MAX]
        print(f"== Running for org={org} seeds={len(seeds)} (max {PER_ORG_MAX}) rotate_circuit={ROTATE_CIRCUIT}")
        for url in seeds:
            try:
                fetch_and_save(org, url, query_text="seed-run", rotate_circuit=ROTATE_CIRCUIT)
            except Exception as e:
                print("Runner: fetch failed:", e)
            # small pause between seeds to be polite (fetch function also pauses per-host)
            time.sleep(0.5)
        print(f"Finished org={org}, sleeping {DELAY_BETWEEN_ORGS}s before next org")
        time.sleep(DELAY_BETWEEN_ORGS)

if __name__ == "__main__":
    # optional: pass org names as args to restrict run to specific orgs
    import sys
    selected = sys.argv[1:] if len(sys.argv) > 1 else None
    run_all(selected)
