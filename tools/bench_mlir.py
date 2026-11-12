#!/usr/bin/env python3
"""Paired benchmark for two real mlir-opt binaries (baseline vs patched)."""
import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from make_wide_dealloc import render, render_observable


def resolve(path: str) -> str:
    found = shutil.which(path) if os.path.sep not in path else str(Path(path).resolve())
    if not found or not Path(found).exists():
        raise FileNotFoundError(f"mlir-opt not found: {path}; see docs/build-and-validation.md")
    return found


def run(binary: str, input_path: Path, with_pass: bool, cpu: str | None) -> float:
    command = [binary, str(input_path), "--mlir-disable-threading"]
    if with_pass:
        command.append("--buffer-deallocation-simplification")
    command += ["-o", os.devnull]
    if cpu is not None:
        taskset = shutil.which("taskset")
        if not taskset:
            raise RuntimeError("--cpu requires taskset")
        command = [taskset, "-c", cpu, *command]
    start = time.perf_counter()
    p = subprocess.run(command, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if p.returncode:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{p.stderr[:4000]}")
    return elapsed


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True, help="path to baseline mlir-opt")
    p.add_argument("--optimized", required=True, help="path to patched mlir-opt")
    p.add_argument("--sizes", nargs="+", type=int, default=[512, 1024, 2048, 4096])
    p.add_argument("--repeats", type=int, default=7)
    p.add_argument("--observable", action="store_true", help="copy into each alloc to keep observable IR")
    p.add_argument("--cpu", default=None, help="optional CPU list passed to taskset, e.g. 2")
    p.add_argument("--out", type=Path, default=ROOT / "results" / "mlir-benchmark.json")
    args = p.parse_args()
    baseline, optimized = resolve(args.baseline), resolve(args.optimized)
    records = []
    for n in args.sizes:
        fixture = ROOT / "benchmarks" / (f"wide-observable-{n}.mlir" if args.observable else f"wide-{n}.mlir")
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(render_observable(n) if args.observable else render(n), encoding="utf-8")
        # Warm both binaries before collecting paired samples.
        run(baseline, fixture, True, args.cpu)
        run(optimized, fixture, True, args.cpu)
        base_total, opt_total, parse_times = [], [], []
        for i in range(args.repeats):
            # Alternate execution order to reduce systematic thermal/frequency bias.
            if i % 2 == 0:
                b = run(baseline, fixture, True, args.cpu)
                o = run(optimized, fixture, True, args.cpu)
            else:
                o = run(optimized, fixture, True, args.cpu)
                b = run(baseline, fixture, True, args.cpu)
            parse = run(baseline, fixture, False, args.cpu)
            base_total.append(b)
            opt_total.append(o)
            parse_times.append(parse)
        base_pass = [b - q for b, q in zip(base_total, parse_times)]
        opt_pass = [o - q for o, q in zip(opt_total, parse_times)]
        paired_speedups = [b / o for b, o in zip(base_pass, opt_pass) if o > 0]
        data = {
            "n": n,
            "baseline_total_s": base_total,
            "optimized_total_s": opt_total,
            "parse_only_s": parse_times,
            "baseline_pass_estimate_s": base_pass,
            "optimized_pass_estimate_s": opt_pass,
            "baseline_total_median_s": statistics.median(base_total),
            "optimized_total_median_s": statistics.median(opt_total),
            "parse_only_median_s": statistics.median(parse_times),
            "baseline_pass_median_s": statistics.median(base_pass),
            "optimized_pass_median_s": statistics.median(opt_pass),
            "paired_pass_speedup_median": statistics.median(paired_speedups) if paired_speedups else None,
        }
        data["total_speedup"] = data["baseline_total_median_s"] / data["optimized_total_median_s"]
        print(
            f"n={n} total {data['baseline_total_median_s']:.4f}s -> "
            f"{data['optimized_total_median_s']:.4f}s "
            f"({data['total_speedup']:.2f}x); parse-subtracted pass estimate "
            f"{data['baseline_pass_median_s']:.4f}s -> "
            f"{data['optimized_pass_median_s']:.4f}s; "
            f"paired speedup={data['paired_pass_speedup_median']:.2f}x"
        )
        records.append(data)
    if args.observable and args.out == ROOT / "results" / "mlir-benchmark.json":
        args.out = ROOT / "results" / "mlir-benchmark-observable.json"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "baseline": baseline,
        "optimized": optimized,
        "baseline_sha256": sha256(baseline),
        "optimized_sha256": sha256(optimized),
        "repeats": args.repeats,
        "cpu_affinity": args.cpu,
        "workload": "observable-copies" if args.observable else "unused-allocations",
        "records": records,
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Results written to: {args.out}")


if __name__ == "__main__":
    main()
