# LLVM/MLIR 源码级集成：最终验证记录（2026-11-12）

## 任务

在 LLVM Issue #219740 对应的固定提交 `902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`，针对 `BufferDeallocationSimplification.cpp` 中处理宽 `bufferization.dealloc` 的近二次方别名检查，加入 allocation-root 计数快速路径；未知来源时保留原有别名分析。

## 实际构建

- LLVM/MLIR `24.0.0git`、WSL Ubuntu 22.04、GCC 11.4、CMake 3.22.1。
- 同一固定提交，两个二进制均真实编译、链接、运行成功，源码补丁应用于 `/home/zwq/llvm-project-src`。
- 原版 SHA-256：`4ae9d3394e3750f3b6b98df8ac54f1fac19cc769e21a180643e5e40c6e5b2953`
- 修改版 SHA-256：`3efcef7bd6814ecc0927ac433bd7acaca733c3d8dbe0b262ae3c429245f1e7f1`
- 新增 FileCheck + LLVM 原有 FileCheck：两版各两组均通过。
- 混合来源、同分配根 view 差分测试：两版输出完全相同。

## Benchmark 结论

**原始 issue 合成负载**：4096 个独立 MemRef，原版总进程中位耗时 6413.8 ms，修改版 468.4 ms，**13.69×**（每版 7 次）。

**保留 `memref.copy` 的非空 IR 负载**：4096 个独立 MemRef，原版 6127.8 ms，修改版 493.9 ms，**12.41×**（每版 5 次）；两版输出的非空 IR 均约 734 KB，SHA-256 相同。

端到端时间包含 `mlir-opt` 启动与解析开销，因此不是精确的单 Pass 计时。对不确定的 allocation root 仍走原逻辑，改进不保证通用最坏情况变为线性。

## 关键路径

- `patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch`
- `modified-source/mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp`
- `tests/llvm/buffer-deallocation-simplification-wide.mlir`
- `tests/llvm/mixed-origin-differential.mlir`
- `tools/integrate_patch.py`
- `tools/bench_mlir.py`
- `results/integration-validation.json`
- `results/mlir-benchmark.json`
- `results/mlir-benchmark-observable.json`
- `results/observable-output-comparison.json`

## 边界与下一步

固定版本和多组现实代码/合成负载已通过构建、FileCheck、字节级 IR 比较；尚未对所有可能的控制流、动态 shape、以及别名场景作形式化证明，也未提交 LLVM 上游。此项目来源于公开 Issue，社区作者已有 allocation-root 原型；贡献应准确描述为独立复现、修改、测试与性能验证。
