# 项目实施状态（2026-11-12）

## 目标

针对 LLVM Issue [#219740](https://github.com/llvm/llvm-project/issues/219740) 中 MLIR `buffer-deallocation-simplification` 的宽 `bufferization.dealloc` 别名检查瓶颈，设计和实现 allocation-root 哈希计数快速路径，并在真实 LLVM/MLIR 源码中复现、编译、回归、测试。

## 已完成

- [x] LLVM 固定提交：`902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`。
- [x] 在 WSL Ubuntu 22.04 编译原始 LLVM/MLIR `mlir-opt` 和 `FileCheck`。
- [x] 对 `BufferDeallocationSimplification.cpp` 实现 `llvm::DenseMap<Value, int64_t>` allocation-root 计数快速路径，无法证明根来源时保守回退。
- [x] 补丁在固定提交上 `patch --dry-run` 检查、实际应用、修改版 `mlir-opt` 编译和链接均成功。
- [x] 原版/修改版均通过新增 FileCheck 以及 LLVM 上游原有回归测试。
- [x] 同分配根 view、不同根、未知来源、混合来源差分测试输出完全一致。
- [x] 512 和 4096 的原始合成负载输出一致；补充保留 `memref.copy` 的非空 IR 输出一致。
- [x] 两类负载均实测真实 `mlir-opt` 端到端耗时，保存各次样本 JSON。
- [x] Python 单元测试 6 项通过，补丁结构检查通过。

## 性能（固定版本、本机实测）

| 用例 | MemRef | 原版（中位数） | 修改版（中位数） | 端到端加速 |
|---|---:|---:|---:|---:|
| Issue 合成复现 | 4096 | 6413.8 ms | 468.4 ms | 13.69× |
| 保留 `memref.copy` 的非空 IR | 4096 | 6127.8 ms | 493.9 ms | 12.41× |

此处为整个 `mlir-opt` 进程耗时，包含进程启动与 IR 解析。结果限于指定合成工作负载，不应泛化为所有程序的编译加速。

## 产物

- 完整补丁：`patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch`
- 新增 LLVM 测试：`tests/llvm/`
- 完整构建与复现说明：`docs/build-and-validation.md`
- 实验报告：`results/final-summary.md`
- 原始样本：`results/mlir-benchmark.json` 和 `results/mlir-benchmark-observable.json`

## 尚未完成

- 尚未向 LLVM 上游提交 Pull Request 或完成上游代码审查。
- 对动态形状、复杂控制流、不同 alias root 分析可证明性仍需进一步覆盖。
- 测试主要是合成工作负载，不包含完整模型编译链端到端对照。

## 贡献来源

优化问题来自 LLVM 社区公开 Issue #219740，社区作者已有原型。本项目是独立复现、源码修改和实测工程验证，不宣称首次发现该问题或首次提出 allocation-root 思路。
