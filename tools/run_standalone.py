#!/usr/bin/env python3
"""Compile and verify the standalone algorithm experiment with system g++."""
from pathlib import Path
import csv
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
build = root / "build"
build.mkdir(exist_ok=True)
binary = build / "alias_split_experiment"
source = root / "src" / "alias_split_experiment.cpp"
subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", str(source), "-o", str(binary)], check=True)
out = ["case,n,baseline_us,optimized_us,speedup,baseline_checks,optimized_checks,splittable"]
for n in [128, 512, 1024, 2048, 4096]:
    p = subprocess.run([str(binary), str(n), "5"], capture_output=True, text=True, check=True)
    out += p.stdout.strip().splitlines()
csv_path = root / "results" / "standalone-benchmark.csv"
csv_path.parent.mkdir(exist_ok=True)
csv_path.write_text("\n".join(out)+"\n",encoding="utf-8")
print("\n".join(out))
print(f"\nWrote: {csv_path}")
