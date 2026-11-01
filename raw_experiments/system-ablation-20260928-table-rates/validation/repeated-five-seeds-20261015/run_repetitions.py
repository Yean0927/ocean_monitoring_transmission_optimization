#!/usr/bin/env python3
"""Run the full eight-variant matrix for independent seeds 32--35.

Seed 31 is assembled from the corrected QUIC smoke runs plus corrected TCP-only
runs and is summarized separately. Outputs are isolated by seed directory.
"""
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RUNNER = EXPERIMENT / "run_experiment.py"
PREPARED = EXPERIMENT / "prepared"
LOG = HERE / "repeat-run.log"
SEEDS = (32, 33, 34, 35)

with LOG.open("a", encoding="utf-8") as log:
    for seed in SEEDS:
        out = HERE / f"seed-{seed}"
        command = [sys.executable, str(RUNNER), "--prepared", str(PREPARED),
                   "--output", str(out), "--seed", str(seed), "--workers", "2"]
        print(f"START seed={seed}", flush=True)
        log.write(f"START seed={seed}\n")
        log.flush()
        start = time.perf_counter()
        subprocess.run(command, cwd=EXPERIMENT, stdout=log, stderr=subprocess.STDOUT,
                       check=True)
        elapsed = time.perf_counter() - start
        line = f"DONE seed={seed} wall_seconds={elapsed:.1f}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
