# 求解器版本、运行方式与实验配置

核对日期为 2026-11-24。本文记录这次 NLIP-AIJ 正式主批使用的求解器、Ubuntu 实际路径、启动参数与运行模式。版本依据官方发布记录和本机实际执行核对，正式实验使用固定版本，不在运行过程中自动更新。

## 1. 唯一开发源与交付副本

唯一开发目录是 `/home/ubuntu/#科研项目/MIS/3-NLIP_AIJ`。本文用 `ROOT` 表示这个完整路径，用 `PYTHON` 表示 `ROOT/.venv-solvers/bin/python`。

`/home/ubuntu/NLIP-Journal-Artifact-publish` 是从 ROOT 选取源码和文档的 GitHub 提交副本。研究开发和测试在 ROOT 完成，交付副本用于生成提交，不在其中独立发展另一套算法。MatriCS 从 GitHub 拉取同一份交付源码。

路径差异来自机器环境。源码应一致，但 MatriCS 的数据、二进制和解释器位置由它自己的 `jobs/config.cluster.json` 指定，不复制广州的绝对路径。

## 2. 版本核对与本次处理

| 求解器或接口 | 本次选用版本 | 官方核对来源 | 本次处理 |
| --- | --- | --- | --- |
| UWrMaxSAT | 2.0.6 | [正式发布 v2.0.6](https://github.com/marekpiotrow/UWrMaxSat/releases/tag/v2.0.6)，2026-08-06 | 从 2.0.0 更新并重新编译，保留 MaxPre 和 SCIP 阶段 |
| MaxHS | 修订版 ASchidler/MaxHS，提交 `b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740` | [维护仓库的对应源码](https://github.com/ASchidler/MaxHS/commit/b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740) | 用核对当日维护分支最新提交重新编译，SCIP 后端 |
| WMaxCDCL | MSE2026 独立版 | [官方 2026 求解器发布包](https://zenodo.org/records/21358014)，`solver-WMaxCDCL2026.zip` | 保留。未找到该独立变体更晚的公开发布 |
| EvalMaxRes | MSE2026 发布版 | [官方 2026 求解器发布包](https://zenodo.org/records/21358014)，`solver-EvalMaxRes.zip` | 保留。未找到该变体更晚的公开发布 |
| CaDiCaL，用于正式 SMT 编码 | 3.1.0 | [正式发布 rel-3.1.0](https://github.com/arminbiere/cadical/releases/tag/rel-3.1.0)，2026-11-17 | 从 PySAT 内置 3.0 调用更新为独立 3.1.0 可执行程序 |
| SCIP | 10.1.0 | [正式发布 v10.1.0](https://github.com/scipopt/scip/releases/tag/v10.1.0) | 已是核对当日最新正式版，保留 |
| PySCIPOpt | 6.3.0 | [官方 PyPI 包](https://pypi.org/project/PySCIPOpt/) | 本机与 PyPI 最新版本一致 |
| Z3 | 5.4.1.0 | [官方 PyPI 包](https://pypi.org/project/z3-solver/) | 本机包和引擎版本一致，已是最新 |
| OR-Tools / CP-SAT | 9.15.6755 | [官方 PyPI 包](https://pypi.org/project/ortools/) | 已是最新，保留 |
| Gurobi | 14.0.0 | [官方 PyPI 包](https://pypi.org/project/gurobipy/) | Python 包与引擎均为 14.0.0，保留 |
| cvc5 | 1.4.2 | [官方 PyPI 包](https://pypi.org/project/cvc5/) | 已是最新，保留 |
| PySAT | 1.9.dev24 | [官方 PyPI 包](https://pypi.org/project/python-sat/) | 最新已发布开发版，保留 |

MaxHS 选用的是仍维护的修订版，不以原 `fbacchus/MaxHS` 仓库的旧发布号替代新维护分支。它没有相应的新语义版本号，因此记录实际源码提交。

EvalMaxRes 和 EvalMaxSAT 是不同变体。EvalMaxRes 包内程序名仍叫 `EvalMaxSAT`，帮助输出也使用该名称；这里依据官方包来源和启动设置识别为 EvalMaxRes，不能按可执行文件名字替换为另一个变体。WMaxCDCL 同样区分独立版与附加 SCIP、Open-WBO 阶段的组合版，本实验保持独立版。

## 3. 实际外部可执行文件

下表中的路径均相对于本页定义的 Ubuntu ROOT，拼接后就是 `jobs/config.cluster.json` 中使用的绝对路径。

| 配置键 | 实际可执行文件 |
| --- | --- |
| `MAXHS` | `solvers/20261124/bin/maxhs` |
| `WMAXCDCL` | `solvers/20261012/WMaxCDCL2026/bin/wmaxcdcl_static` |
| `UWRMAXSAT` | `solvers/20261124/bin/uwrmaxsat` |
| `EVALMAXRES` | `solvers/20261123/EvalMaxRes/EvalMaxSAT` |
| EvalMaxRes 辅助程序 | `solvers/20261123/EvalMaxRes/nuwls` |
| `CADICAL` | `solvers/20261124/bin/cadical` |
| SCIP 共享库 | `solvers/20261012/scipoptsuite-10.1.0/lib64/libscip.so.10.1.0` |

新版 MaxHS 直接调用二进制，不再通过原来隐含 SCIP 参数的包装脚本。运行模式参数统一显式保存在 `external_solver_args`。

主批使用 Python API 的基线不另外启动 `z3`、`gurobi_cl`、`scip` 或 `cvc5` 命令行程序。统一由 `PYTHON` 启动 worker，再导入对应模块。模块实际位置为 `ROOT/.venv-solvers/lib/python3.12/site-packages/` 下的 `z3/`、`ortools/`、`gurobipy/`、`pyscipopt/` 和 `cvc5/`。这也是为什么仅查看系统 PATH 中的求解器版本不足以确认本实验实际使用的版本。

## 4. 外部求解器启动参数与模式

以下 `<formula.wcnf>` 和 `<formula.cnf>` 表示某个实例运行时生成的公式。具体命令保存在该实例的 `result.json` 的 `external_command` 字段中。

### MaxHS

```text
maxhs -printSoln -printSoln-old-format -optimizer=scip -no-lp-harden-reduced <formula.wcnf>
```

实际参数顺序以结果中的命令为准。`-optimizer=scip` 选择 SCIP 10.1.0 优化后端，`-no-lp-harden-reduced` 保留维护者 README 针对已知问题给出的设置。打印解参数由 NLIP 适配器添加，以便原问题验解。采用普通 SCIP 模式，没有切换到 `scip_exact`，也没有调用 CPLEX。

### WMaxCDCL

```text
wmaxcdcl_static <formula.wcnf>
```

使用 MSE2026 独立程序的默认搜索设置，不附加 SCIP/Open-WBO 组合阶段。正式运行由父进程控制墙钟时间，因此不另加一个竞争的 CPU 超时参数。

### UWrMaxSAT

```text
uwrmaxsat -no-bin -no-sat -no-par -maxpre-time=60 -scip-cpu=900 -scip-cpu-add=400 -m -bm <formula.wcnf>
```

采用 2.0.6 正式版，MaxPre 已编入，SCIP 已连接到 10.1.0。`-no-par` 禁止 SCIP 与主算法并行求解，保留顺序 SCIP 阶段。900 和 400 是该阶段的内部时间设置，MaxPre 内部预算为 60 秒；这些阶段全部包含在实例统一的 3600 秒墙钟预算内，不另加实验时间。`-m -bm` 请求供适配器读取的模型输出。

本机 `UWRFLAGS` 环境变量未设置。正式交接也保持未设置，避免用隐含环境选项覆盖记录的启动参数。

UWrMaxSAT 2.0.6 内部使用按其构建接口编入的 CaDiCaL 3.0.0，并应用上游 UWr 提供的 conflicts 接口补丁。这是 UWr 的内部依赖；正式 SMT 主实验独立调用的是 CaDiCaL 3.1.0。MaxHS 源码同样自带其固定的 CaDiCaL 3.0.0。更新顶层求解器时保留其内部依赖接口，不把每个嵌入式组件替换成另一套实现。

### EvalMaxRes

```text
EvalMaxSAT --noSaveCores --noSimplify --path_anytime_solver <nuwls绝对路径> <formula.wcnf>
```

保留官方 MSE2026 exact 配置，使用包内 nuwls 辅助程序产生上界。辅助程序的位置明确传入，不依赖运行目录。`--timeUB` 未覆盖，官方程序帮助显示默认 180 秒；这仍属于统一实例时间预算的一部分。父进程监督整棵进程树。

### CaDiCaL

```text
cadical <formula.cnf>
```

使用独立 3.1.0 的默认顺序 SAT 模式。适配器要求 SAT/UNSAT 状态与 10/20 退出码一致，对 SAT 模型先检查 CNF，再做 NLIP 原问题验解。公式写出、进程启动和结果读取均计入统一时间。

旧的独立开发 CLI 在未指定 `--sat-path` 或 `NLIP_CADICAL` 时，仍支持 PySAT 内置的 `cadical300`。正式主批会检查配置中的 `CADICAL` 可执行文件，因此不会静默回退到 3.0。

## 5. Python 基线的实际参数

| 基线 | 模式及主要参数 |
| --- | --- |
| SCIP-native | 整数多项式直接建模；`parallel/maxnthreads=1`，`randomization/randomseedshift=0`，`numerics/feastol=1e-9`，`limits/gap=0`，`limits/absgap=0`，`limits/time` 为剩余预算 |
| CP-SAT | 整数变量和乘积约束，目标和约束的有理系数做精确整数缩放；`num_search_workers=1`，`random_seed=0`，`max_time_in_seconds` 为剩余预算 |
| Gurobi | 有界整数多项式及乘积辅助变量；`Threads=1`，`Seed=0`，`NonConvex=2`，`MIPGap=0`，`MIPGapAbs=0`，`FeasibilityTol=1e-9`，`IntFeasTol=1e-9`，`TimeLimit` 为剩余预算 |
| Z3 | 保留现有优化与判定流程；优化使用 Optimize 及后续已实现的证明/改进检查，SMT 使用现有 solver 路线；每阶段 timeout 使用剩余预算 |
| cvc5 | 仅 SMT 判定；`produce-models=true`，`incremental=true`，`seed=0`，`tlimit-per` 为剩余毫秒 |

所有 worker 绑定一个物理核。可行解回到原问题验解，并重新计算原始目标。UNSAT 记录后端终态，没有为每个实例增加独立 UNSAT 证明检查。

RC2、GLUCOSE 以及代码中保留的其他历史基线不属于此次正式主批。RC2 的开发接口来自当前 PySAT；本轮没有将它们重新加入正式配置。

## 6. 到底在哪里修改配置

| 要修改什么 | 修改位置 | 说明 |
| --- | --- | --- |
| 选择哪些数据族、编码、求解器 | `jobs/internal/experiment.py` | 唯一正式矩阵定义，当前 58 配置、22,220 次调用 |
| 实例列表 | `benchmarks/manifests/` | 四个正式清单，保持本批口径 |
| 数据位置、Python、求解器实际程序 | 本机 `jobs/config.cluster.json` | `benchmark_root`、`families.*.input_root`、`python`、`solver_paths` |
| 外部程序启动参数 | 同上 | `external_solver_args` |
| 已核实的版本和模式说明 | 同上 | `solver_metadata`。改文字不等于升级程序，必须安装对应程序并更新路径 |
| 单实例时间、内存、验解预算 | 同上 | `profiles.formal` |
| Python 包版本 | `jobs/requirements-core.txt`、`jobs/requirements-baselines.txt` | 修改后需在实际解释器中安装并测试 |
| 分区、并行数、同时运行配置数 | `jobs/generate_scripts.py` 顶部常量或命令行参数 | 优先用 `--partition`、`--workers`、`--concurrent-jobs` |
| 本批已冻结的实际配置 | `results/<批次>/campaign.json` | 由生成器产生，运行中不手工改它 |

`jobs/config.json` 是新机器的配置起点；`config.cluster.json` 存在时优先使用后者。`jobs/tools/configure_cluster.py` 负责把本站路径写入配置，不负责从网上下载或自动升级求解器。

## 7. bigmem 与 bigmem-amd

当前默认使用 `bigmem-amd`。根据 [MatriCS 官方分区说明](https://www.matrics.u-picardie.fr/en/documentation-2/partitions/)，bigmem 每节点 28 核、512 GB，bigmem-amd 每节点 64 核、1 TB，CPU 平台也不同。

58 是实验配置总数，60 是一个正式配置内最多同时处理的实例数，同时运行配置数为 1。当前 bigmem-amd 的正式设置为 60 个工作进程、970 GiB、独占节点，最大配置申请 19 小时。

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py \
  --partition bigmem-amd --workers 60 --concurrent-jobs 1 \
  --output results/main-new-solvers
```

若确定改用 bigmem，示例如下。生成器会按 28 × 16 GiB 加余量申请 450 GiB，并重新估算作业时间，当前最大配置约 38 小时。

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py \
  --partition bigmem --workers 28 --concurrent-jobs 1 \
  --output results/main-new-solvers-bigmem
```

改变分区会改变 CPU 平台，同一正式对比应统一在所选平台运行。不能只改分区名却保留超过节点核数的 60 个工作进程。实际分区可用性和账户配额在 MatriCS 用 `sinfo`、`scontrol show partition` 确认。本轮保持 bigmem-amd 默认值。

## 8. 编译与交接说明

新编译的 UWrMaxSAT、MaxHS 和 CaDiCaL 位于 ROOT 的 `solvers/20261124/bin/`。源码分别来自本页固定的 tag 或提交，编译使用优化配置。UWr 与 MaxHS 动态连接现有 SCIP 10.1.0，构建时使用与该 SCIP 安装配套的 MPFR 库，并优先使用系统 C++ 运行库。编译日志和源码保存在 ROOT 的 `solvers/20261124/` 及 `/home/ubuntu/nlip-solver-build-20261124/`，后者仅是第三方软件编译目录。

这些 Ubuntu 二进制并非脱离系统依赖的通用包。MatriCS 安装相同 tag/源码提交并连接本站对应库，或使用经计算节点验证兼容的二进制。不要只拷贝新主程序而遗漏 SCIP 与依赖库。MatriCS 配置中的五个外部程序路径和实际模式均需按本文对应项填写。

源代码交付包括新的 SAT 适配器、实验配置工具、测试和本文。外部二进制、编译目录、Python 环境、许可证、原始数据和运行结果不混入 GitHub 源码提交。Gurobi 当前广州安装仍是受限许可证，正式 MatriCS 实验需要完整许可证。

## 9. 升级后的最终测试

在上述最终二进制路径和参数下，2026-11-24 于广州重新执行完整小测与相关检查。

| 验证 | 结果 |
| --- | --- |
| 58 个配置经执行模板实际求解 | 52 OPTIMAL、6 SAT，已知答案和原问题验解全部通过 |
| 运行器、后端适配与分析测试 | 41 项通过，包括新版 CaDiCaL 与独立穷举的对照 |
| 核心测试 | 50 项通过 |
| 公共 API | 56/56 通过 |
| 续跑 | 已完成结果保持原记录 |
| 汇总与绘图 | 正常完成 |
| bigmem-amd 正式计划 | 58 配置、22,220 次调用，60 工作进程、970 GiB |
| bigmem 备选计划 | 同一矩阵，28 工作进程、450 GiB |

最终结果和实际启动命令保存在 Ubuntu `ROOT/results/solver-refresh-20261124/`。旧的 `handoff-20261124/` 是升级前检查，不混作新版结果。58 次小测覆盖四个已知答案输入的全部配置组合，未开始正式 22,220 次性能运行。

GitHub 提交准备不包含站点配置和二进制。合作者在 MatriCS 按本表部署后，再通过计算节点小测和完整 Gurobi 许可证检查，才开始正式实验。
