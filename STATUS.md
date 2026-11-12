# 项目状态

**LLVM 固定提交：** `902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`
**开发环境：** WSL2 / Ubuntu 22.04 / GCC 11.4 / Release + Assertions
**核心模块：** `SplitDeallocWhenNotAliasingAnyOther`

## 已完成

- [x] 定位宽 `bufferization.dealloc` 的 O(N²) 别名检查瓶颈。
- [x] 实现 Allocation Root 统计快速路径，保留未知来源下的原有别名分析。
- [x] 在固定 LLVM/MLIR 源码中应用补丁并构建 `mlir-opt`。
- [x] 原版和优化版通过 LLVM 上游与新增 FileCheck 回归测试。
- [x] 验证独立根、同根 view、未知根及混合来源的 IR 输出一致性。
- [x] 完成 512–4096 个 MemRef 的原始负载与非空 IR 负载 Benchmark。
- [x] 保存逐次测量、SHA-256 校验和构建记录。
- [x] 六项 Python 单元测试通过。

## 关键数据

| 工作负载（4096 MemRef） | 原版 | 优化版 | 加速 |
|---|---:|---:|---:|
| 宽 `dealloc` | 6413.8 ms | 468.4 ms | 13.69× |
| 含 `memref.copy` | 6127.8 ms | 493.9 ms | 12.41× |

测量口径：完整 `mlir-opt` 进程耗时，中位数；详细样本在 `results/`。

## 后续工作

- 扩展不同控制流与动态 MemRef 来源的测试覆盖。
- 分析已知/未知根混合时的局部快速路径。
- 使用更大规模神经网络导出的 IR 进行编译性能评估。
- 整理补丁以符合 LLVM 上游代码风格和评审要求。

详见 [README](README.md)、[技术分析](docs/problem-analysis.md) 和 [实验报告](results/final-summary.md)。
