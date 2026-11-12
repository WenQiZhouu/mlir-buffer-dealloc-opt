# LLVM/MLIR Buffer Deallocation Pass 优化实验报告

## 项目目标

优化 MLIR `buffer-deallocation-simplification` Pass 对宽 `bufferization.dealloc` 的别名分析开销。针对 `SplitDeallocWhenNotAliasingAnyOther` 重复复制 operand 列表和重复执行别名查询的瓶颈，增加 Allocation Root 计数快速路径。

相关问题：[LLVM Issue #219740](https://github.com/llvm/llvm-project/issues/219740)

## 代码实现

- **优化位置：** `mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp`
- **根来源分析：** `getViewBase` + `memref::AllocOp`
- **数据结构：** `llvm::DenseMap<Value, int64_t>`
- **优化策略：** 唯一根直接拆分、共享根保留组合、未知根进入原别名分析路径
- **复杂度：** 全部根已知时，候选检查由近 O(N²) 降至 O(N)

## 编译与测试环境

| 项目 | 配置 |
|---|---|
| LLVM 提交 | `902c28258ab67d9095e5b8dbf51dce7d0c90d9a7` |
| 构建 | Release + Assertions |
| 系统 | WSL2 / Ubuntu 22.04 |
| 编译器 | GCC 11.4 |
| 工具 | CMake、mlir-opt、FileCheck、Python 3 |

原版与修改版 `mlir-opt` 均完成源码构建和链接，相关回归、差分用例通过。

## 性能对比：原始宽 dealloc

*完整进程中位耗时，每组重复 7 次。*

| MemRef 数量 | 原版 | 优化版 | 端到端加速 |
|---:|---:|---:|---:|
| 512 | 518.3 ms | 424.4 ms | 1.22× |
| 1024 | 784.5 ms | 433.9 ms | 1.81× |
| 2048 | 1850.9 ms | 429.2 ms | 4.31× |
| 4096 | 6413.8 ms | 468.4 ms | **13.69×** |

数据文件：[mlir-benchmark.json](mlir-benchmark.json)

## 性能对比：含实际内存操作的非空 IR

每个分配增加 `memref.copy`，确保输出保留内存操作。

*完整进程中位耗时，每组重复 5 次。*

| MemRef 数量 | 原版 | 优化版 | 端到端加速 |
|---:|---:|---:|---:|
| 512 | 511.9 ms | 449.2 ms | 1.14× |
| 1024 | 797.4 ms | 436.0 ms | 1.83× |
| 2048 | 1861.5 ms | 458.0 ms | 4.06× |
| 4096 | 6127.8 ms | 493.9 ms | **12.41×** |

4096 MemRef 时，两版输出约 734 KB 的非空 MLIR，SHA-256 一致。

数据文件：[mlir-benchmark-observable.json](mlir-benchmark-observable.json)

## 回归测试

- LLVM 上游 `buffer-deallocation-simplification.mlir` 测试
- 新增独立分配根、共享 View、未知来源测试
- 新增共享根与独立根、已知与未知来源混合差分测试
- 512/4096 输入的转换结果 SHA-256 对比
- Python 生成器、补丁检查测试

验证记录：[integration-validation.json](integration-validation.json)、[mixed-origin-differential.json](mixed-origin-differential.json)、[observable-output-comparison.json](observable-output-comparison.json)。

## 文件与命令

- C++ 优化补丁：`patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch`
- 回归测试：`tests/llvm/`
- 性能脚本：`tools/bench_mlir.py`
- 构建过程：[docs/build-and-validation.md](../docs/build-and-validation.md)

性能口径为完整 `mlir-opt` 进程，测量包含启动和 IR 解析。
