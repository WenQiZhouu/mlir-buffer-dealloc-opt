# LLVM 上游 PR 准备

## Title

[mlir][bufferization] Avoid quadratic alias checks for wide deallocs with known allocation roots

## Pull request description

### Summary

`SplitDeallocWhenNotAliasingAnyOther` currently rebuilds the remaining operand list and performs pairwise alias checks for every memref in a `bufferization.dealloc`. For a wide dealloc with distinct allocation roots, this work scales quadratically with the number of operands.

This patch introduces an allocation-root fast path:

- Trace each candidate operand through `getViewBase` to a `memref.alloc` root.
- Count occurrences of each root using `llvm::DenseMap<Value, int64_t>`.
- When all roots are known, determine whether a memref can split off by checking if its root occurs exactly once.
- Keep the existing alias-analysis path for inputs with unknown origins.

The fast path avoids N copies of the operand list and N(N-1) pairwise checks for distinct allocation roots.

### Benchmark

Measured with Release + Assertions `mlir-opt` on WSL2 (median total command runtime):

| MemRefs | Baseline | Patched | Speedup |
|---:|---:|---:|---:|
| 512 | 0.518 s | 0.424 s | 1.22x |
| 1024 | 0.785 s | 0.434 s | 1.81x |
| 2048 | 1.851 s | 0.429 s | 4.31x |
| 4096 | 6.414 s | 0.468 s | 13.69x |

For an input with a `memref.copy` for each allocated buffer (nonempty transformed IR), 4096 memrefs improved from 6.128 s to 0.494 s (12.41x).

### Testing

- Built baseline and patched `mlir-opt` successfully from LLVM revision `902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`.
- Passed the existing `buffer-deallocation-simplification.mlir` test.
- Passed the new FileCheck cases for distinct allocation roots, aliased views sharing a root, unknown origins, and mixed cases.
- Verified identical transformed IR between baseline and patched binaries for the tested cases.

Fixes #219740.
