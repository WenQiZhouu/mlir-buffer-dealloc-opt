#!/usr/bin/env python3
"""Reproducer adapted from LLVM issue #219740 (attributed in README)."""
import argparse
from pathlib import Path

def render(n: int) -> str:
    if n < 2:
        raise ValueError("n must be >= 2")
    names = [f"%a{i}" for i in range(n)]
    lines = ["module {", "  func.func @f() {", "    %true = arith.constant true"]
    lines.extend(f"    {x} = memref.alloc() : memref<1xi8>" for x in names)
    lines.append("    bufferization.dealloc (" + ", ".join(names) +
                 " : " + ", ".join(["memref<1xi8>"] * n) + ") if (" +
                 ", ".join(["%true"] * n) + ")")
    lines += ["    return", "  }", "}"]
    return "\n".join(lines) + "\n"


def render_observable(n: int) -> str:
    """A wide dealloc whose allocated buffers have observable memory writes.

    Keeps allocations and deallocs in the transformed IR instead of letting
    the canonicalizer remove the entire unused alloc/dealloc pair.
    """
    if n < 2:
        raise ValueError("n must be >= 2")
    names = [f"%a{i}" for i in range(n)]
    lines = ["module {", "  func.func @f(%src: memref<1xi8>, %cond: i1) {"]
    lines.extend(f"    {x} = memref.alloc() : memref<1xi8>" for x in names)
    lines.extend(f"    memref.copy %src, {x} : memref<1xi8> to memref<1xi8>" for x in names)
    lines.append("    bufferization.dealloc (" + ", ".join(names) +
                 " : " + ", ".join(["memref<1xi8>"] * n) + ") if (" +
                 ", ".join(["%cond"] * n) + ")")
    lines += ["    return", "  }", "}"]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("n", type=int, help="number of distinct allocations")
    p.add_argument("--output", type=Path)
    p.add_argument("--observable", action="store_true", help="add real memref.copy uses")
    args = p.parse_args()
    data = render_observable(args.n) if args.observable else render(args.n)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
        print(args.output)
    else:
        print(data, end="")

if __name__ == "__main__":
    main()
