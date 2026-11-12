# MLIR Buffer Deallocation Pass 优化

基于 LLVM/MLIR 官方源码的编译器性能优化项目。针对 `buffer-deallocation-simplification` 在大规模 MemRef 释放场景下的重复别名分析问题，实现基于 Allocation Root 的快速路径，并完成源码构建、回归测试和编译性能评估。

**相关问题：** [LLVM Issue #219740](https://github.com/llvm/llvm-project/issues/219740)
**LLVM 固定提交：** `902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`
**实现语言：** C++17、Python 3
**工具链：** LLVM/MLIR、CMake、GCC、FileCheck、WSL2

## 问题分析

核心位置：

```text
mlir/lib/Dialect/Bufferization/Transforms/
  BufferDeallocationSimplification.cpp

SplitDeallocWhenNotAliasingAnyOther
```

当一条 `bufferization.dealloc` 包含大量 MemRef 时，原 Pass 针对每一个候选 MemRef，重新创建剩余 MemRef 列表，并检查其与其他 operand 的别名关系。

对于 N 个彼此独立的分配，列表复制与别名检查的总开销接近 **O(N²)**，导致宽 `dealloc` 的编译时间快速增长。

## 优化实现

在原 C++ Rewrite Pattern 内增加 Allocation Root 分析：

1. 使用 `getViewBase` 追溯 MemRef 的 ViewLike 链，判断能否定位到 `memref.alloc`。
2. 通过 `llvm::DenseMap<Value, int64_t>` 统计每个 Allocation Root 在 operand 列表中的出现次数。
3. 当所有 operand 都能确定分配根时，利用根的出现次数判断是否与其他待释放 operand 存在别名：唯一根走直接拆分路径，共享根保留原组合。
4. 存在未知来源时，使用原有别名分析路径处理，保证转换条件符合既有逻辑。

已知分配根的场景中，判定复杂度由近似 **O(N²)** 降至 **O(N)**，同时保留原有 IR Rewrite 的后续处理流程。

核心文件：

- [源码补丁](patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch)
- [修改后的完整 C++ 文件](modified-source/mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp)
- [问题与算法分析](docs/problem-analysis.md)

## 性能结果

在同一台 WSL2 主机上，使用同一固定 LLVM 提交构建原版与优化版 `mlir-opt`，交替运行并取多次测量中位数。

| MemRef 数量 | 原版 | 优化版 | 加速比 |
|---:|---:|---:|---:|
| 512 | 518.3 ms | 424.4 ms | 1.22× |
| 1024 | 784.5 ms | 433.9 ms | 1.81× |
| 2048 | 1850.9 ms | 429.2 ms | 4.31× |
| 4096 | 6413.8 ms | 468.4 ms | **13.69×** |

以上为**完整 `mlir-opt` 进程的中位耗时**，包含启动、解析和 Pass 执行；每组重复 7 次。

进一步加入 `memref.copy`，确保输出保留实际内存操作。在 4096 个 MemRef 的非空 IR 用例中，耗时从 **6127.8 ms** 降至 **493.9 ms**，加速 **12.41×**（每组重复 5 次），两版生成 IR 完全一致。

原始数据：

- [基础 Benchmark](results/mlir-benchmark.json)
- [非空 IR Benchmark](results/mlir-benchmark-observable.json)
- [实验报告](results/final-summary.md)

## 正确性与工程验证

- 在真实 LLVM/MLIR 源码中应用补丁，完成修改版 `mlir-opt` 的编译与链接。
- 通过 LLVM 原有 FileCheck 回归用例和新增测试。
- 检查独立分配根、同根 `subview`、未知根及混合来源场景。
- 对比两版生成 IR 的 SHA-256，验证所测场景的输出一致性。
- 使用 Python 单元测试覆盖复现生成器与补丁结构。

详细记录见 [构建与验证文档](docs/build-and-validation.md) 和 [集成验证数据](results/integration-validation.json)。

## 复现实验

在 Ubuntu 22.04 / WSL2 中：

```bash
cd /mnt/d/runfiles/mlir-buffer-dealloc-opt

# 生成 4096 个 MemRef 的 MLIR 输入
python3 tools/make_wide_dealloc.py 4096 \
  --output benchmarks/wide-4096.mlir

# 使用独立 C++ 模型检查别名判定逻辑
python3 tools/run_standalone.py

# 运行 Python 测试
python3 -m unittest discover -s tests -v
```

完成 [LLVM/MLIR 构建](docs/build-and-validation.md) 后，对比真实二进制：

```bash
python3 tools/bench_mlir.py \
  --baseline build-artifacts/mlir-opt-baseline \
  --optimized build-artifacts/mlir-opt-patched \
  --sizes 512 1024 2048 4096 --repeats 7

# 包含 memref.copy 的非空 IR 用例
python3 tools/bench_mlir.py \
  --baseline build-artifacts/mlir-opt-baseline \
  --optimized build-artifacts/mlir-opt-patched \
  --sizes 512 1024 2048 4096 --repeats 5 --observable
```

## 项目结构

```text
src/                    C++ 别名判定实验
patches/                LLVM C++ Pass 补丁及回归测试
modified-source/        修改后的 Pass 源码
reference-tree/         固定提交的原始 Pass 源码
tests/llvm/             MLIR FileCheck 和差分测试
tests/                  Python 单元测试
tools/                  复现生成、集成验证和性能测试
docs/                   原理与构建文档
results/                Benchmark 数据及实验报告
```

LLVM 原始源码保留项目原有许可声明（Apache-2.0 WITH LLVM-exception）。
