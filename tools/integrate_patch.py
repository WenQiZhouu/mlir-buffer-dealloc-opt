#!/usr/bin/env python3
"""Capture a baseline mlir-opt, apply the local patch, rebuild, and test both."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get("LLVM_SRC", "/home/zwq/llvm-project-src"))
BUILD = Path(os.environ.get("LLVM_BUILD", "/home/zwq/llvm-build"))
PATCH = ROOT / "patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch"
WIDE_TEST = ROOT / "tests/llvm/buffer-deallocation-simplification-wide.mlir"
UPSTREAM_TEST = SRC / "mlir/test/Dialect/Bufferization/Transforms/buffer-deallocation-simplification.mlir"
PASS_SOURCE = SRC / "mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp"
EXPECTED_SOURCE = ROOT / "modified-source/mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp"
RESULTS = ROOT / "results"
ARTIFACTS = ROOT / "build-artifacts"
FILECHECK = BUILD / "bin/FileCheck"


def run(cmd: list[str], cwd: Path | None = None, log: Path | None = None) -> str:
    print("+", " ".join(map(str, cmd)), flush=True)
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as f:
            p = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, text=True)
        output = log.read_text(encoding="utf-8", errors="replace")
    else:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output = p.stdout
    if p.returncode:
        print(output[-12000:], flush=True)
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str, cmd))}")
    return output


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(binary: Path, test: Path, label: str) -> Path:
    opt = run([str(binary), str(test), "--verify-each",
               "--buffer-deallocation-simplification", "--split-input-file"])
    checked = subprocess.run([str(FILECHECK), str(test)], input=opt,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if checked.returncode:
        print(checked.stdout[-10000:], flush=True)
        raise RuntimeError(f"FileCheck failed: {label} / {test}")
    out = RESULTS / f"{label}-{test.stem}.mlir"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(opt, encoding="utf-8")
    print("PASS", label, test.name, "output_bytes", len(opt), flush=True)
    return out


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    baseline = ARTIFACTS / "mlir-opt-baseline"
    patched = ARTIFACTS / "mlir-opt-patched"
    live_binary = BUILD / "bin/mlir-opt"

    if not live_binary.exists() or not FILECHECK.exists():
        raise FileNotFoundError("Build mlir-opt and FileCheck first; see docs/build-and-validation.md")

    # Preserve the unmodified binary before touching the source.
    if not baseline.exists():
        shutil.copy2(live_binary, baseline)
    print("BASELINE_SHA256", sha256(baseline), flush=True)

    baseline_wide = validate(baseline, WIDE_TEST, "baseline")
    validate(baseline, UPSTREAM_TEST, "baseline-upstream")

    current = PASS_SOURCE.read_text(encoding="utf-8")
    expected = EXPECTED_SOURCE.read_text(encoding="utf-8")
    if current != expected:
        dry = run(["patch", "--dry-run", "-p1", "-i", str(PATCH)], cwd=SRC)
        print(dry, flush=True)
        run(["patch", "-p1", "-i", str(PATCH)], cwd=SRC)
    else:
        print("Patch source already matches the prepared modified-source snapshot.", flush=True)

    actual_hash = sha256(PASS_SOURCE)
    expected_hash = sha256(EXPECTED_SOURCE)
    if actual_hash != expected_hash:
        raise RuntimeError("Applied C++ source differs from the prepared modified-source snapshot")

    build_log = RESULTS / "build-patched.log"
    run(["cmake", "--build", str(BUILD), "--target", "mlir-opt", "--parallel", "4"], log=build_log)
    shutil.copy2(live_binary, patched)
    print("PATCHED_SHA256", sha256(patched), flush=True)

    patched_wide = validate(patched, WIDE_TEST, "patched")
    validate(patched, UPSTREAM_TEST, "patched-upstream")

    same_output = baseline_wide.read_bytes() == patched_wide.read_bytes()
    report = {
        "llvm_source": str(SRC),
        "llvm_build": str(BUILD),
        "baseline_binary": str(baseline),
        "patched_binary": str(patched),
        "baseline_sha256": sha256(baseline),
        "patched_sha256": sha256(patched),
        "patched_source_sha256": actual_hash,
        "wide_test_output_identical": same_output,
        "wide_test": str(WIDE_TEST),
        "upstream_test": str(UPSTREAM_TEST),
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    report_path = RESULTS / "integration-validation.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    if not same_output:
        raise RuntimeError("Baseline and patched MLIR outputs differ; inspect saved .mlir files")


if __name__ == "__main__":
    main()
