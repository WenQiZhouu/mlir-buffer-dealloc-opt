# Buffer Deallocation Pass 性能问题与优化设计

相关 LLVM 问题：[Issue #219740](https://github.com/llvm/llvm-project/issues/219740)

## 1. 问题定位

ONNX-MLIR 在编译 DenseNet-121 时出现一条包含 2547 个 MemRef operand 的 `bufferization.dealloc`。在固定 LLVM 提交 `902c28258ab67d9095e5b8dbf51dce7d0c90d9a7` 中，主要开销集中在：

```text
mlir/lib/Dialect/Bufferization/Transforms/BufferDeallocationSimplification.cpp
  SplitDeallocWhenNotAliasingAnyOther
```

原实现逐个处理待释放 MemRef，并对每个候选重新构建剩余 operand 列表、查询别名关系。

对于 N 个来源独立的 MemRef：

- 反复复制 operand 列表：O(N²)
- 多次调用别名判定：接近 N(N−1) 次
- 结果：Pass 耗时随待释放 operand 数量呈近二次增长

## 2. 实现方案

### Allocation Root 分析

`getViewBase(memref)` 沿 ViewLike 操作追溯内存来源。所有待释放 operand 的根均能够确定为 `memref.alloc` 时，使用根唯一性代替成对别名检查。

```cpp
llvm::DenseMap<Value, int64_t> rootUseCount;
SmallVector<Value> knownRoots;

for (Value memref : deallocOp.getMemrefs()) {
  Value root = getViewBase(memref);
  if (!root.getDefiningOp<memref::AllocOp>()) {
    allRootsKnown = false;
    break;
  }
  knownRoots.push_back(root);
  ++rootUseCount[root];
}
```

### 快速路径与回退路径

- **唯一 Allocation Root：** 与其他已知根独立，可拆分处理。
- **相同 Allocation Root 多次出现：** 多个 View 共享底层分配，维持组合处理。
- **存在未知根：** 调用原有 `potentiallyAliasesMemref` 路径。

核心优化不调整后续 Deallocation Rewrite，而是替换热点中的拆分条件判定。

### 复杂度

| 路径 | 时间复杂度 | 主要操作 |
|---|---|---|
| 原始全量别名检查 | 近 O(N²) | 列表复制、逐对分析 |
| 全部根已知 | O(N) | 根遍历、DenseMap 计数、查表 |
| 存在未知根 | 原有复杂度 | 原始别名分析 |

## 3. 测试覆盖

| 用例 | 检查内容 |
|---|---|
| N 个独立 `memref.alloc` | 快速拆分，测试复杂度 |
| 两个同根 `memref.subview` | 共享分配不被错误独立处理 |
| 未知来源函数参数 | 原别名分析路径 |
| 同根 View + 独立分配 | 混合已知根的处理 |
| 已知根 + 未知根 | 回退路径 |
| 每个分配带 `memref.copy` | 非空生成 IR 和编译耗时 |

使用 LLVM FileCheck 测试和两版 `mlir-opt` 输出 SHA-256 对比进行验证。

## 4. 性能分析

4096 个独立 MemRef 的真实 `mlir-opt` 端到端中位耗时：

- 原版：6413.8 ms
- 修改版：468.4 ms
- 加速：**13.69×**

添加 `memref.copy` 的非空 IR 工作负载：

- 原版：6127.8 ms
- 修改版：493.9 ms
- 加速：**12.41×**

两组数据均包含 `mlir-opt` 进程启动、IR 解析和 Pass 执行开销，原始样本见 `results/`。

## 5. 源码与复现

- [完整 C++ 补丁](../patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch)
- [MLIR 回归测试](../tests/llvm/buffer-deallocation-simplification-wide.mlir)
- [构建与验证](build-and-validation.md)
- [实验记录](../results/final-summary.md)
