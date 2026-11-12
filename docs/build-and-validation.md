# LLVM / MLIR 真实集成与构建记录

## 固定版本

- 仓库：llvm/llvm-project
- Commit：`902c28258ab67d9095e5b8dbf51dce7d0c90d9a7`
- D 盘归档：`D:\\runfiles\\mlir-buffer-dealloc-opt\\vendor\\llvm-project-902c28258ab67d9095e5b8dbf51dce7d0c90d9a7.tar.gz`
- SHA-256：`145e7f90fd2f256838c5b85e7bf1b5be5305c1e798d591a2ae6cdc588fad5af9`
- WSL 源码树：`/home/zwq/llvm-project-src`
- WSL 构建目录：`/home/zwq/llvm-build`

D 盘保存源码归档、补丁、测试和结果；大规模 CMake 中间文件放在 WSL ext4 文件系统，避免 NTFS 挂载目录的编译 I/O 开销。

## 当前机器环境

- Ubuntu 22.04 / WSL2
- GCC 11.4.0
- CMake 3.22.1
- 6 vCPU，约 11 GiB WSL 可用内存
- 使用 Unix Makefiles；Ninja 不可用
- 不依赖 sudo

LLVM 源码在 CMake 配置阶段要求根目录下的 `libc` 公共工具，即使没有启用 libc 项目也会检查 `llvm-libc-common-utilities`。因此源码解压除 `llvm/`、`mlir/`、`cmake/`、`third-party/` 外，还要包含根目录 `libc/`。

## 从 D 盘归档重新解压

```bash
ARCHIVE=/mnt/d/runfiles/mlir-buffer-dealloc-opt/vendor/llvm-project-902c28258ab67d9095e5b8dbf51dce7d0c90d9a7.tar.gz
SRC=/home/zwq/llvm-project-src
mkdir -p "$SRC"
tar -xzf "$ARCHIVE" -C "$SRC" --strip-components=1 \
  --no-same-owner --no-same-permissions --wildcards \
  'llvm-project-902c28258ab67d9095e5b8dbf51dce7d0c90d9a7/llvm/*' \
  'llvm-project-902c28258ab67d9095e5b8dbf51dce7d0c90d9a7/mlir/*' \
  'llvm-project-902c28258ab67d9095e5b8dbf51dce7d0c90d9a7/cmake/*' \
  'llvm-project-902c28258ab67d9095e5b8dbf51dce7d0c90d9a7/third-party/*' \
  'llvm-project-902c28258ab67d9095e5b8dbf51dce7d0c90d9a7/libc/*'
```

## CMake 配置

```bash
cmake -S /home/zwq/llvm-project-src/llvm \
  -B /home/zwq/llvm-build \
  -G "Unix Makefiles" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_CXX_STANDARD=17 \
  -DLLVM_ENABLE_PROJECTS=mlir \
  -DLLVM_TARGETS_TO_BUILD=Native \
  -DLLVM_ENABLE_ASSERTIONS=ON \
  -DLLVM_INCLUDE_TESTS=ON \
  -DMLIR_INCLUDE_TESTS=OFF \
  -DLLVM_BUILD_EXAMPLES=OFF
```

本固定提交在当前 CMake 3.22.1 下配置成功。CMake 会提示 LLVM 24 起最低版本将提升到 3.31；这是前向兼容警告，不影响本提交当前配置。

## 构建原版 mlir-opt

```bash
cmake --build /home/zwq/llvm-build \
  --target mlir-opt FileCheck --parallel 4
```

原版二进制必须在应用补丁之前保存（脚本实际保存在 D 盘）：

```bash
cp /home/zwq/llvm-build/bin/mlir-opt \
   /mnt/d/runfiles/mlir-buffer-dealloc-opt/build-artifacts/mlir-opt-baseline
```

## 应用补丁并构建修改版

在固定版本源码根目录执行：

```bash
cd /home/zwq/llvm-project-src
patch --dry-run -p1 -i \
  /mnt/d/runfiles/mlir-buffer-dealloc-opt/patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch
patch -p1 -i \
  /mnt/d/runfiles/mlir-buffer-dealloc-opt/patches/0001-avoid-quadratic-alias-checks-for-known-roots.patch
cmake --build /home/zwq/llvm-build \
  --target mlir-opt --parallel 4
cp /home/zwq/llvm-build/bin/mlir-opt \
   /mnt/d/runfiles/mlir-buffer-dealloc-opt/build-artifacts/mlir-opt-patched
```

## 回归测试

新测试文件：
`tests/llvm/buffer-deallocation-simplification-wide.mlir`

测试三个关键场景：
1. 不同 `memref.alloc` 根可以拆分。
2. 同一 allocation root 的两个 subview 不得被错误拆分。
3. 来源未知的函数参数必须走原始保守别名分析。

```bash
PROJECT=/mnt/d/runfiles/mlir-buffer-dealloc-opt
BUILD=/home/zwq/llvm-build
"$BUILD/bin/mlir-opt" "$PROJECT/tests/llvm/buffer-deallocation-simplification-wide.mlir" \
  --verify-each --buffer-deallocation-simplification --split-input-file \
  | "$BUILD/bin/FileCheck" "$PROJECT/tests/llvm/buffer-deallocation-simplification-wide.mlir"
```

还要运行上游已有测试：

```bash
TEST=/home/zwq/llvm-project-src/mlir/test/Dialect/Bufferization/Transforms/buffer-deallocation-simplification.mlir
"$BUILD/bin/mlir-opt" "$TEST" --verify-each \
  --buffer-deallocation-simplification --split-input-file \
  | "$BUILD/bin/FileCheck" "$TEST"
```

原版和修改版都必须通过以上测试。另应将二者输出保存并比较，确认改写结果一致。

## 真实编译耗时对比

```bash
python3 /mnt/d/runfiles/mlir-buffer-dealloc-opt/tools/bench_mlir.py \
  --baseline /mnt/d/runfiles/mlir-buffer-dealloc-opt/build-artifacts/mlir-opt-baseline \
  --optimized /mnt/d/runfiles/mlir-buffer-dealloc-opt/build-artifacts/mlir-opt-patched \
  --sizes 512 1024 2048 4096 --repeats 7
```

脚本交替运行 baseline / patched，分别记录 parse-only 和 pass 总耗时，并计算扣除解析耗时后的 pass 估算值。只有真实两个 `mlir-opt` 都构建成功且回归通过后，才能将数据作为 LLVM Pass 性能结果。

## 构建日志

日志统一保存到：
- `results/cmake-configure.log`
- `results/build-baseline-j4.log`
- 后续修改版日志及真实 Benchmark JSON / CSV

不要将独立 C++ 算法模型的速度提升写成 MLIR 编译器的实测加速。


## 已通过的集成验证与测试结果（2026-11-12）

```bash
python3 /mnt/d/runfiles/mlir-buffer-dealloc-opt/tools/integrate_patch.py
# 报告：/mnt/d/runfiles/mlir-buffer-dealloc-opt/results/integration-validation.json
```

- 原版与修改版 mlir-opt 均实际编译并成功链接；二者二进制 SHA-256 不同。
- 新增的 FileCheck 测试和 LLVM 上游原有测试：原版、修改版均通过。
- 两版的新增测试文本输出完全一致，未知来源与同分配根的情况保守处理。
- 补充的混合来源差分测试：两版输出相同。
- 压力用例 512/4096 MemRef：两版输出 SHA-256 相同（输出为可消除的空模块，不足以独立证明所有语义）。

### 实际 benchmark

| N | baseline 中位耗时 | patched 中位耗时 | 总进程加速 |
|---:|---:|---:|---:|
| 512 | 0.5183 s | 0.4244 s | 1.22x |
| 1024 | 0.7845 s | 0.4339 s | 1.81x |
| 2048 | 1.8509 s | 0.4292 s | 4.31x |
| 4096 | 6.4138 s | 0.4684 s | 13.69x |

单次测量、parse-only 估计等详见 `results/mlir-benchmark.json`。对于报告和简历，推荐优先引用 13.69x 总进程加速；不将估计的 Pass 独立加速比作为严格测量。


## 非空 IR 的补充验证（2026-11-12）

用 `memref.copy` 保留每个分配的实际内存操作，不让输出在该 Pass 中全部化简为空模块：

```bash
cd /mnt/d/runfiles/mlir-buffer-dealloc-opt
python3 tools/bench_mlir.py \
  --baseline build-artifacts/mlir-opt-baseline \
  --optimized build-artifacts/mlir-opt-patched \
  --sizes 512 1024 2048 4096 --repeats 5 --observable
```

| N | 原版总进程中位值 | 修改版总进程中位值 | 加速 |
|---:|---:|---:|---:|
| 512 | 0.5119 s | 0.4492 s | 1.14x |
| 1024 | 0.7974 s | 0.4360 s | 1.83x |
| 2048 | 1.8615 s | 0.4580 s | 4.06x |
| 4096 | 6.1278 s | 0.4939 s | 12.41x |

结果：`results/mlir-benchmark-observable.json`。512/4096 的输出均已用 SHA-256 比较，两版完全相同；4096 输出约 734 KB 的非空 IR（`results/observable-output-comparison.json`）。
