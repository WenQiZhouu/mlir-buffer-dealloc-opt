# MLIR Buffer Deallocation Optimization

> 项目位置：`D:\runfiles\mlir-buffer-dealloc-opt`（WSL：`/mnt/d/runfiles/mlir-buffer-dealloc-opt`）

## 研究问题与来源

基于 LLVM 社区公开的 [Issue #219740](https://github.com/llvm/llvm-project/issues/219740)：
`-buffer-deallocation-simplification` 在一个包含大量 MemRef 的
`bufferization.dealloc` 上出现接近 O(N^2) 的编译耗时。

原始热点：`mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp`
中的 `SplitDeallocWhenNotAliasingAnyOther`。

社区 Issue 作者已提出 allocation-root 优化原型；本项目是在该公开问题上的
独立学习、源码分析与实现实验，不宣称首次发现或原创发明。

固定参考提交：`902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`。

## 当前阶段（2026-11-12）

- [x] 获取并保存固定提交的上游 Pass 源文件。
- [x] 提供官方格式的可参数化 MLIR 复现生成器。
- [x] 构建独立 C++ 别名决策模型（独立分配、重复根、未知根）。
- [x] 编写 C++ 真实源码差异补丁（allocation-root 计数快速路径 + 保守回退）。
- [x] 提供 `mlir-opt` 对照 Benchmark 与语义比较脚本。
- [x] 在 LLVM 目标提交完整构建并编译此补丁。
- [x] 在真实 `mlir-opt` 上回归 FileCheck/IR 输出，并完成真实端到端耗时对比。
- [ ] 扩充复杂别名与分支场景，决定是否值得 upstream 贡献。

**注意**：`src/alias_split_experiment.cpp` 是用于验证算法思路的独立
C++ 模型，**不是**已经运行过的 MLIR Pass；编译器性能必须在真实
`mlir-opt` 上独立验证。具体执行情况以 `results/` 下结果为准。

## 一分钟启动（不需要管理员权限）

在 WSL Ubuntu 22.04：

```bash
cd /mnt/d/runfiles/mlir-buffer-dealloc-opt

# 1. 构建+运行独立 C++ 算法实验
python3 tools/run_standalone.py

# 2. 生成官方形式 MLIR 复现
python3 tools/make_wide_dealloc.py 4096 \
  --output benchmarks/wide-4096.mlir

# 3. 检查补丁是否能应用在保存的原始源文件上
git apply --check --directory=reference-tree patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch
```

## 真实 LLVM/MLIR 集成验证（本机实测，2026-11-12）

- LLVM 固定提交：`902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`（MLIR/LLVM 24.0.0git）。
- 构建：WSL Ubuntu 22.04、GCC 11.4、Release + Assertions、Native X86。
- 原版/修改版二进制：`build-artifacts/mlir-opt-baseline`、`build-artifacts/mlir-opt-patched`。
- 真实源码补丁已应用到 `/home/zwq/llvm-project-src`，修改版 `mlir-opt` 成功增量编译并链接（退出码 0）。
- 新增根来源/同源视图/未知来源测试，以及上游原有回归测试，两版均通过 FileCheck；测试输出 IR 完全一致。
- 另外对“同根分组+独立分配”“已知+未知来源混合”的差分测试，两版也都正常执行并输出完全一致。
- 对 512 和 4096 个 MemRef 的压力输入，输出 IR 的 SHA-256 完全相同；压力输入中的 allocation/deallocation 是可被消去的，因而不能把该检查当作广泛的内存语义证明。
- 具体构建、日志、每次测试数据和 SHA-256：`docs/build-and-validation.md`、`results/`。

### 真实端到端耗时（每规模 7 次，中位数）

| N（MemRef） | 原版 mlir-opt | 修改版 mlir-opt | 端到端加速 |
| --: | --: | --: | --: |
| 512 | 518.3 ms | 424.4 ms | 1.22× |
| 1024 | 784.5 ms | 433.9 ms | 1.81× |
| 2048 | 1850.9 ms | 429.2 ms | 4.31× |
| 4096 | 6413.8 ms | 468.4 ms | **13.69×** |

测的是 **mlir-opt 从启动、解析到 Pass 完成的整体进程耗时**，不是单独 Pass 的精确计时。测试脚本同时记录了不跑 Pass 的基线；相减得到的 Pass 耗时只是一种近似估计，不能忽略系统抖动。尤其 4096 组原版减去 parse-only 约为 5.93 s，修改版约为 0.013 s，但不建议将两者直接相除来宣传“数百倍加速”。简历与报告更适合使用已测得的 **13.69× 端到端**提升，并注明是特定合成负载。

原始数据：`results/mlir-benchmark.json`；实际执行与通过记录：`results/integration-validation.json`、`results/mixed-origin-differential.json`、`results/stress-output-comparison.json`。

### 保留内存操作的非空 IR 补充基准（每规模 5 次，中位数）

与上面的原始 Issue 复现不同，此测试对每个 `memref.alloc` 添加 `memref.copy`，避免生成的整个内存操作序列被消去。

| N（MemRef） | 原版 mlir-opt | 修改版 mlir-opt | 端到端加速 |
| --: | --: | --: | --: |
| 512 | 511.9 ms | 449.2 ms | 1.14× |
| 1024 | 797.4 ms | 436.0 ms | 1.83× |
| 2048 | 1861.5 ms | 458.0 ms | 4.06× |
| 4096 | 6127.8 ms | 493.9 ms | **12.41×** |

4096 规模下两版各输出约 734 KB 的非空 IR，SHA-256 完全相同；这是可观察内存操作下的更直接输出对照，但仍属于合成负载。结果见 `results/mlir-benchmark-observable.json` 和 `results/observable-output-comparison.json`。

```bash
python3 tools/bench_mlir.py \
  --baseline build-artifacts/mlir-opt-baseline \
  --optimized build-artifacts/mlir-opt-patched \
  --sizes 512 1024 2048 4096 --repeats 5 --observable
```

### 重新执行验证和 Benchmark

```bash
cd /mnt/d/runfiles/mlir-buffer-dealloc-opt
# 已构建两个二进制后直接运行
python3 tools/bench_mlir.py \
  --baseline build-artifacts/mlir-opt-baseline \
  --optimized build-artifacts/mlir-opt-patched \
  --sizes 512 1024 2048 4096 --repeats 7
```

**限制**：当前只有固定提交和合成分配图工作负载验证；对更多复杂分支、动态形状、大规模未知 root 需要进一步测试；尚未提交/合并到 LLVM 上游。

## 目录

- `upstream-reference/`：精确提交的原始 C++ 源文件（版权归 LLVM 项目）。
- `reference-tree/`：以 LLVM 相同目录层级保存的基线，供 `git apply --check`。
- `modified-source/`：已生成的修改版完整 C++ 文件，方便查看差异。
- `patches/`：准备应用到 LLVM 原仓库的源代码补丁。
- `tools/`：复现生成器、算法实验和真实 `mlir-opt` benchmark。
- `benchmarks/`：可参数化的 MLIR 测试数据。
- `results/`：本机运行数据（真实/模拟数据严格区分）。
- `docs/`：技术分析、实验方法、构建指南。

## 核心方案

原始实现对每个 MemRef 拷贝其他所有 operands 并逐一调用别名分析。
自定义补丁先对已知 `memref.alloc` 根（以及可追溯的 ViewLike 链）计数：

- 某个已知根只出现一次：可与其他已知根区分，采用直接分离路径。
- 某个根出现多次：保留该别名组，不做不安全的独立释放重写。
- 任一根不确定：全体回退到原有别名分析逻辑，优先确保语义正确。

这个快速路径主要优化全部来源可证明的情况；对包含不确定来源的情况
仍可能保持原始近 O(N^2) 的复杂度，后续再评估改进。

## License / provenance

LLVM 项目源码文件保留原许可声明（Apache-2.0 WITH LLVM-exception）。
复现问题来自社区 Issue #219740。独立编写的实验工具是学习用途。
