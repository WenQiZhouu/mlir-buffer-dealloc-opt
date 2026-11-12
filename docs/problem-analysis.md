# Issue #219740 根因分析与优化设计

## 来源

LLVM Issue: https://github.com/llvm/llvm-project/issues/219740

问题来自 ONNX-MLIR DenseNet-121 编译，其中一条
`bufferization.dealloc` 拥有 2547 个 MemRef operand。
目标提交：`902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`。

## 原始算法

对每个 MemRef：
1. 复制全部 operands，删除当前 operand。
2. 遍历其余 N-1 个 MemRef，判断是否可能别名。
3. 如果可证明与其他所有 operand 无别名，生成单独 dealloc。

在 N 个独立分配根的输入上：
- 复制总成本为 O(N²)
- 别名检查调用近 N(N-1) 次
- 实际 Pass 耗时近似二次增长

## 这个补丁的优化策略

对于能回溯到 `memref.alloc` 的 MemRef，使用 `getViewBase`
剥离 ViewLike 链，取得可证明的分配根。

若所有 operands 均能证明来自 `memref.alloc`：
- 使用 `DenseMap<Value, int64_t>` 建立每个根出现的次数。
- 根出现一次的 operand，可以与所有其他根证明为 no-alias。
- 根重复出现的 operands 不能独立拆分。
- 根不确定，完全回退原有代码路径以避免误判。

时间复杂度（已知根）约 O(N)，空间 O(N)。
如果根不确定，仍可能是原有的 O(N²)。

## 关键正确性前提

- 每个独立 `memref.alloc` 代表不同的底层 allocation。
- ViewLike 链不会改变底层 allocation 来源。
- 只有能够证明的 no-alias 才可用于独立拆分。
- 对无法证明来源的 Select、BlockArgument 或未知指针，不能仅凭不同 SSA Value 认定 no-alias。
- 其他 retained operands 的更新与原始 Rewrite 保持一致；本补丁只替换 split eligibility 判断。

## 实验纪律

Issue 作者的现有原型数据 **不是** 本项目结果。
`src/alias_split_experiment.cpp` 的基准结果 **不是** MLIR 端到端耗时。
必须额外对真实 `mlir-opt` 比较：编译时间、IR 相同性、变换合法性、
多消费者/重复 root / subview / 未知来源等边界情况。
