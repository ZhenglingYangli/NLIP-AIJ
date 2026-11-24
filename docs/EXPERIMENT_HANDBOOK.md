# NLIP-AIJ 实验方案与 MatriCS 完整操作手册

更新日期为 2026-11-24。本文面向接手实验的合作者，集中说明实验方案、求解器、源码结构和操作步骤。命令按顺序在 MatriCS 的 Linux 终端执行，除非段落明确写了广州或 Windows。命令中的“请填写”必须替换成实际值。

## 阅读顺序

- 第 1 部分明确本次跑什么、跑多少、怎样计时和判定结果。
- 第 2 部分记录固定求解器版本、广州实际程序、启动参数和模式。
- 第 3 部分说明各目录、主要文件和开发交付位置。
- 第 4 部分从新建目录、GitHub 拉取开始，部署环境并完成小测和正式运行。
- 第 5 部分说明如何修改路径、资源、版本和实验组合，以及续跑、收结果。
- 第 6 部分记录交付验证与正式运行前仍需在 MatriCS 完成的事项。

日常只使用两个入口。`jobs/generate_scripts.py` 生成作业，`jobs/goSolver.py` 运行实例。实验组合定义统一保存在 `jobs/internal/experiment.py`，NLIP 和 DiverseSAT 均采用这组文件名及位置。

## 1. 实验方案与配置

### 1.1 正式主批

| 数据族 | 输入数 | 编码及后端 | 直接建模基线 | 配置数 | 运行数 |
| --- | ---: | --- | --- | ---: | ---: |
| QPLIB | 137 | OH、UNA、BIN × MaxHS、WMaxCDCL、UWrMaxSAT、EvalMaxRes | SCIP-native、Z3、CP-SAT、Gurobi | 16 | 2,192 |
| DiverseSAT 应用模型，k=2 | 108 | 同上 | 同上 | 16 | 1,728 |
| MIPO | 870 | OH、UNA、BIN、BIN+D × 上述四后端 | 同上 | 20 | 17,400 |
| 有界 SMT | 150 | OH、UNA、BIN、BIN+D × CaDiCaL | Z3、cvc5 | 6 | 900 |
| 合计 | 1,265 | | | 58 | 22,220 |

BIN+D 使用已有分解设置。SCIP、Gurobi 和 CP-SAT 直接接收有界整数多项式模型，非线性乘积通过相应乘积约束或有界中间变量表达。cvc5 用于 SMT 判定。核心仍保留 RC2 开发与回归接口，但主批不选 RC2、Open-WBO、CPLEX 或两条 MILP 扩展路线。

独立的共享消融为 MIPO/WMaxCDCL 和 SMT/CaDiCaL 共 1,020 次运行，与主批分开。

### 1.2 资源与计时

58 是全部实验配置的数量。60 是一个配置内的并行工作进程上限。这两者属于不同层次。

以 QPLIB 的 BIN + WMaxCDCL 为例，137 个实例最多有 60 个同时运行，其余等待空闲工作进程。配置的全部实例结束后，数组才开始下一个配置。正式数组为 `0-57%1`，有 58 个元素，同时最多执行一个元素。

| 层次 | 资源或数量 |
| --- | --- |
| 全部配置 | 58 个 |
| 同时运行配置 | 1 个 |
| 每配置并行实例 | 最多 60 个 |
| 每实例 | 1 个物理核、16 GiB |
| 每配置 Slurm 申请 | 独占 bigmem-amd 节点，60 核、970 GiB |
| 最长配置的预留时间 | 19 小时 |
| 单实例预算 | 启动、解析、编码、求解合计 3600 秒，验解另给 120 秒，外围 4000 秒 |

小测每个配置只有一个输入，使用一个工作进程，每个 Slurm 元素申请五分钟。Ubuntu 对数组执行路径的验证按单进程依次执行；60 个实例并行时的集群资源分配需要在 MatriCS 验证。

### 1.3 执行和验解

生成器展开实例清单并记录本批方法与预算。提交后，Slurm 分配资源，`goSolver.py` 取得对应配置，内部运行器逐个启动 worker。worker 解析输入，进行预处理和编码或直接建模，再调用后端。监督器从进程启动开始计时，控制整棵进程树的资源。后端返回可行解时进入单独的验解阶段，核对原始约束和目标。

每个实例的 `result.json` 记录终态、时间、模型信息及可用的赋值证据。全部结束后汇成 `results.csv`，再生成 `analysis/` 和 `sumup/`。OPTIMAL、FEASIBLE、SAT、UNSAT、TIMEOUT、OOM、INVALID、LICENSE_LIMIT 和 UNSUPPORTED 分开保留；没有终态记录的是 PENDING。

SAT 或可行优化解必须通过原问题验解。UNSAT 没有可行赋值可验，本套实验记录后端的不可行终态，不提供每个 UNSAT 的独立证明检查。公开参考解核对和小域穷举测试用于验证相关接口与建模语义。

### 1.4 正式统计口径

优化任务只有 `OPTIMAL` 且原问题验解通过才计入“解出”。只有可行解时记为 `FEASIBLE`，不会计为已证明最优。SMT 的 `SAT` 必须有验解通过的赋值；`UNSAT` 记录求解器终态。`TIMEOUT`、`OOM`、`UNSUPPORTED`、`LICENSE_LIMIT`、`ERROR`、`INVALID` 分开保留。`PENDING` 表示尚无终态记录。

论文分析时间使用 `solve_wall_seconds`，包含启动、解析、建模或编码以及求解。原问题验解时间单独记录。完整配置的 PAR-2 将未成功的运行按两倍求解预算计入；仍有 PENDING 的配置暂不计算 PAR-2。小测时间不作为论文性能结果。

主批分解方法 BIN+D 使用阈值 3、顺序分解、精确乘法和子结构共享。共享消融仅将 `decomp_shared` 改为 false，保持其余设置相同。主批和消融均关闭 LRN，既有 LRN 2,040 条正式原始记录保持只读。

## 2. 求解器版本、程序与运行方式

本次固定下列版本。后续出现新发布时，先决定是否开启新的性能批次，再更换程序。运行期间不自动追踪最新版。

本文以 `ROOT=/home/ubuntu/#科研项目/MIS/3-NLIP_AIJ` 表示广州活动目录。以下广州路径用于说明已测程序；MatriCS 由自己的 `jobs/config.cluster.json` 指向本站安装。

### 2.1 版本与来源

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

### 2.2 广州实际可执行文件

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

### 2.3 外部程序的完整启动参数

以下 `<formula.wcnf>` 和 `<formula.cnf>` 表示某个实例运行时生成的公式。具体命令保存在该实例的 `result.json` 的 `external_command` 字段中。

#### MaxHS

```text
maxhs -printSoln -printSoln-old-format -optimizer=scip -no-lp-harden-reduced <formula.wcnf>
```

实际参数顺序以结果中的命令为准。`-optimizer=scip` 选择 SCIP 10.1.0 优化后端，`-no-lp-harden-reduced` 保留维护者 README 针对已知问题给出的设置。打印解参数由 NLIP 适配器添加，以便原问题验解。采用普通 SCIP 模式，没有切换到 `scip_exact`，也没有调用 CPLEX。

#### WMaxCDCL

```text
wmaxcdcl_static <formula.wcnf>
```

使用 MSE2026 独立程序的默认搜索设置，不附加 SCIP/Open-WBO 组合阶段。正式运行由父进程控制墙钟时间，因此不另加一个竞争的 CPU 超时参数。

#### UWrMaxSAT

```text
uwrmaxsat -no-bin -no-sat -no-par -maxpre-time=60 -scip-cpu=900 -scip-cpu-add=400 -m -bm <formula.wcnf>
```

采用 2.0.6 正式版，MaxPre 已编入，SCIP 已连接到 10.1.0。`-no-par` 禁止 SCIP 与主算法并行求解，保留顺序 SCIP 阶段。900 和 400 是该阶段的内部时间设置，MaxPre 内部预算为 60 秒；这些阶段全部包含在实例统一的 3600 秒墙钟预算内，不另加实验时间。`-m -bm` 请求供适配器读取的模型输出。

本机 `UWRFLAGS` 环境变量未设置。正式交接也保持未设置，避免用隐含环境选项覆盖记录的启动参数。

UWrMaxSAT 2.0.6 内部使用按其构建接口编入的 CaDiCaL 3.0.0，并应用上游 UWr 提供的 conflicts 接口补丁。这是 UWr 的内部依赖；正式 SMT 主实验独立调用的是 CaDiCaL 3.1.0。MaxHS 源码同样自带其固定的 CaDiCaL 3.0.0。更新顶层求解器时保留其内部依赖接口，不把每个嵌入式组件替换成另一套实现。

#### EvalMaxRes

```text
EvalMaxSAT --noSaveCores --noSimplify --path_anytime_solver <nuwls绝对路径> <formula.wcnf>
```

保留官方 MSE2026 exact 配置，使用包内 nuwls 辅助程序产生上界。辅助程序的位置明确传入，不依赖运行目录。`--timeUB` 未覆盖，官方程序帮助显示默认 180 秒；这仍属于统一实例时间预算的一部分。父进程监督整棵进程树。

#### CaDiCaL

```text
cadical <formula.cnf>
```

使用独立 3.1.0 的默认顺序 SAT 模式。适配器要求 SAT/UNSAT 状态与 10/20 退出码一致，对 SAT 模型先检查 CNF，再做 NLIP 原问题验解。公式写出、进程启动和结果读取均计入统一时间。

旧的独立开发 CLI 在未指定 `--sat-path` 或 `NLIP_CADICAL` 时，仍支持 PySAT 内置的 `cadical300`。正式主批会检查配置中的 `CADICAL` 可执行文件，因此不会静默回退到 3.0。

### 2.4 Python 基线和资源设置

| 基线 | 模式及主要参数 |
| --- | --- |
| SCIP-native | 整数多项式直接建模；`parallel/maxnthreads=1`，`randomization/randomseedshift=0`，`numerics/feastol=1e-9`，`limits/gap=0`，`limits/absgap=0`，`limits/time` 为剩余预算 |
| CP-SAT | 整数变量和乘积约束，目标和约束的有理系数做精确整数缩放；`num_search_workers=1`，`random_seed=0`，`max_time_in_seconds` 为剩余预算 |
| Gurobi | 有界整数多项式及乘积辅助变量；`Threads=1`，`Seed=0`，`NonConvex=2`，`MIPGap=0`，`MIPGapAbs=0`，`FeasibilityTol=1e-9`，`IntFeasTol=1e-9`，`TimeLimit` 为剩余预算 |
| Z3 | 保留现有优化与判定流程；优化使用 Optimize 及后续已实现的证明/改进检查，SMT 使用现有 solver 路线；每阶段 timeout 使用剩余预算 |
| cvc5 | 仅 SMT 判定；`produce-models=true`，`incremental=true`，`seed=0`，`tlimit-per` 为剩余毫秒 |

所有 worker 绑定一个物理核。可行解回到原问题验解，并重新计算原始目标。UNSAT 记录后端终态，没有为每个实例增加独立 UNSAT 证明检查。

RC2、GLUCOSE 以及代码中保留的其他历史基线不属于此次正式主批。RC2 的开发接口来自当前 PySAT；本轮没有将它们重新加入正式配置。

Python 主环境为 3.12。固定依赖为 `python-sat[pb]==1.9.dev24`、`pindakaas==0.6.1`、`z3-solver==5.4.1.0`、`psutil==7.2.2`、`pyscipopt==6.3.0`、`numpy==2.5.4`、`cvc5==1.4.2`、`ortools==9.15.6755`、`gurobipy==14.0.0`，绘图使用 `matplotlib==3.9.4`。

Python 基线通过 `jobs/config.cluster.json` 的 `python` 启动，每个实例的入口为 `jobs/internal/worker.py <job.json>`。它导入对应 Python 接口，不另行调用 `z3`、`gurobi_cl` 或 `scip` 命令行程序。实际解释器和外部命令分别记录在 `result.json` 的 `command` 和 `external_command` 中。环境与版本记录在各配置的 `run.json` 中。

## 3. 代码位置、文件结构与职责

### 3.1 开发到运行的路径

| 位置 | 职责 |
| --- | --- |
| 广州 `/home/ubuntu/#科研项目/MIS/3-NLIP_AIJ` | 实际开发、修复和 Ubuntu 测试 |
| 广州 `/home/ubuntu/NLIP-Journal-Artifact-publish` | 从活动目录选取正式源码，准备 GitHub 提交 |
| GitHub `ZhenglingYangli/NLIP-Journal-Artifact-` | 向合作者交付代码 |
| MatriCS `/scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-` | 合作者拉取代码后生成本站计划并运行 |
| Windows `D:/Users/yang/Documents/ChatGPT/NLIP-AIJ/AIJ写作/04-AIJ实验运行` | 当前源码和说明的本地查阅镜像 |

Ubuntu 开发、GitHub 同步、MatriCS 拉取一直是同一条链。单独的 publish 目录只用于整理提交内容。它不会自动推送，也不是另一套正式实验。

### 3.2 文件结构

```text
项目根目录/
├── README.md
├── jobs/
│   ├── generate_scripts.py       生成器
│   ├── goSolver.py               运行器入口
│   ├── config.json               随仓库交付的配置起点
│   ├── config.cluster.json       本站路径、版本与参数，不进 GitHub
│   ├── requirements*.txt         Python 依赖
│   ├── smoke/                    四个已知答案的小输入
│   ├── internal/
│   │   ├── experiment.py         唯一实验矩阵与输入清单展开逻辑
│   │   ├── run_slurm.sh          Slurm 执行模板
│   │   ├── run_campaign_task.py  数组序号对应到配置，检查续跑条件
│   │   ├── runner.py             并行调度、CPU 分配、结果保存与续跑
│   │   ├── supervisor.py         监督进程树的时间、内存和终止
│   │   └── worker.py             读取一个任务，调用求解器并验解
│   ├── tools/                   首次配置、环境检查、输入检查
│   └── data/                    MIPO 数据准备与转换工具
├── codes/
│   ├── codes/tools/             输入解析、预处理、精确算术和验解
│   ├── codes/encoders/           OH、UNA、BIN 与分解编码
│   ├── codes/solver/             SAT/MaxSAT 调用、终态与模型读取
│   ├── nlipsat/                 对外 Python API
│   ├── solvers/baseline/         SCIP、Z3、CP-SAT、Gurobi、cvc5 适配
│   └── tests/                   求解核心与接口测试
├── benchmarks/manifests/        正式实例清单
├── analysis/                    汇总、统计表、图和结果导出
├── tests/                       实验运行、资源限制和统计测试
├── docs/                        本说明和 MatriCS 手册
└── results/                     本机产生的日志和结果，不进源码提交
```

Python 环境、外部求解器二进制、许可证和原始数据留在各自机器上。以上目录结构不会要求操作者逐个执行内部脚本。

### 3.3 主要文件功能

| 文件 | 功能和修改时机 |
| --- | --- |
| `jobs/generate_scripts.py` | 检查依赖和输入，生成任务计划与提交命令；默认分区、并行数在顶部，日常优先用命令行参数覆盖 |
| `jobs/goSolver.py` | 小测、单配置执行和 Slurm 数组入口 |
| `jobs/internal/experiment.py` | 方法组合、配置读取、实例展开、任务编号；修改科研方案时才改 |
| `jobs/internal/run_campaign_task.py` | 取出数组元素对应的配置并调用运行器 |
| `jobs/internal/runner.py` | 并行分发、物理核绑定、环境记录、结果保存与续跑 |
| `jobs/internal/supervisor.py` | 进程树时间和内存控制、终止清理、阶段计时 |
| `jobs/internal/worker.py` | 解析单个任务、调用编码或基线、验解并输出结果 |
| `jobs/internal/run_slurm.sh` | 计算节点执行模板，由生成的提交脚本调用 |
| `jobs/config.json` | 新机器的配置起点，随 GitHub 交付 |
| `jobs/config.cluster.json` | 本站路径、程序、参数、预算及版本，不提交 GitHub |
| `jobs/requirements*.txt` | 主环境固定依赖；`jobs/environment/` 记录旧环境，仅作历史参考 |
| `jobs/tools/configure_cluster.py` | 将环境变量和已有路径写入本站配置，检查正式输入是否齐全 |
| `jobs/tools/check_environment.py` | 检查 Python 包版本、可导入性及 SCIP 本体版本 |
| `jobs/tools/check_final_inputs.py` | 检查输入清单，解析多项式数据；不运行正式性能实验 |
| `jobs/data/prepare_mipo.py`、`convert_mipo.py` | MIPO 数据准备与 JSON 转换；正式重跑复用已冻结的 870 个 JSON |
| `benchmarks/manifests/*.txt` | 四个正式实例清单；SMT 主批使用 `smt_list_small.txt` |
| `codes/codes/encoders/onehot.py`、`unary.py`、`binary.py` | OH、UNA、BIN 编码 |
| `codes/codes/encoders/constraints.py`、`decomposition.py`、`encoder_driver.py` | 约束编码、乘积分解、编码调度 |
| `codes/codes/tools/*_parser.py`、`dimacs.py` | QPLIB、CNF/DiverseSAT 和 SMT 输入解析 |
| `codes/codes/tools/preprocessing.py`、`arithmetic.py`、`verify.py` | 预处理、精确算术与目标恢复、原问题验解 |
| `codes/codes/solver/config.py` | 编码选项和 BIN+D 预设；正式方法选择仍由实验配置模块控制 |
| `codes/codes/solver/solve.py`、`sat.py` | MaxSAT、SAT 调用以及状态与模型读取 |
| `codes/solvers/baseline/` | SCIP、Z3、CP-SAT、Gurobi 和 cvc5 等适配，部分历史基线保留作开发用途 |
| `codes/nlipsat/` | Python API 与命令行包入口 |
| `codes/telemetry.py` | 运行阶段、模型规模和求解质量记录 |
| `analysis/summarize.py`、`summarize_campaign.py`、`result_table.py` | 单配置与整批结果汇总，保留失败和缺失项 |
| `analysis/analyze_campaign.py`、`run_campaign_analysis.sh` | 配置统计、成对比较、曲线图和分析作业 |
| `analysis/export_results.py`、`push_results.sh` | 可选结果交付工具；原始结果另行保留 |
| `tests/test_*.py`、`codes/tests/` | 可复用回归测试，验证接口、语义、资源控制和统计；不是正式性能输入 |
| `jobs/smoke/` | 四个已知答案的小模型，组合成 58 配置小测 |

DiverseSAT 也使用 `jobs/generate_scripts.py`、`jobs/goSolver.py`、`jobs/internal/experiment.py`。DiverseSAT 保留独立编码作业及分阶段提交，NLIP 在一次受限运行内计时。这一区别来自两套实验的计时口径。

### 3.4 GitHub 提交范围

提交源码、配置模板、固定依赖、实例清单、四个小测输入、可复用回归测试和操作文档。Python 缓存、虚拟环境、构建产物、求解器二进制、许可证、本站配置、原始数据、日志和测试结果保留在本机。历史一次性诊断 `tests/check_*.py` 不作为本次交付入口。

## 4. 合作者从零开始在 MatriCS 运行

### 4.1 登录与新建项目目录

在你自己的电脑上登录 MatriCS，下面的 `你的MatriCS登录地址` 使用账户提供的实际地址。

```bash
ssh 你的MatriCS登录地址
```

以下命令均在 MatriCS 登录节点执行。使用计算节点可访问的共享存储。`/scratch/scherif` 是当前合作者的路径，换账户时修改这部分。

```bash
mkdir -p /scratch/scherif/NLIP/AIJ
cd /scratch/scherif/NLIP/AIJ
git clone https://github.com/ZhenglingYangli/NLIP-Journal-Artifact-.git
cd NLIP-Journal-Artifact-
git log -1 --oneline
ls jobs/generate_scripts.py jobs/goSolver.py jobs/internal/experiment.py
```

已有目录时先确认没有使用它的运行中实验，然后执行 `git status --short` 和 `git pull --ff-only`。如果有源码修改或提示不能快进，保留文件并联系负责人处理。不要重新 clone 到同名非空目录。

### 4.2 首次部署的分工

请合作者或集群管理员提供以下实际位置。带“请填写”的示例必须替换后再执行。

- 本站 Python 3.12 的路径或模块名。
- 已安装的 SCIP 10.1.0 及其头文件、动态库所在目录。
- MaxHS、WMaxCDCL、UWrMaxSAT、EvalMaxRes、CaDiCaL 3.1.0、nuwls 的可执行文件位置、发行版本和模式。
- 原来的 QPLIB、DiverseSAT、SMT 数据位置，以及 870 个已转换 MIPO JSON 文件目录。
- 计算节点可用的完整 Gurobi 许可证。

数据、求解器二进制和许可证不随 GitHub 下载。广州当前选用的具体版本和模式见本文第 2 部分。其中 UWrMaxSAT 已更新为 2.0.6，正式 SMT 使用独立 CaDiCaL 3.1.0，MaxHS 使用维护分支的新提交。MatriCS 按该版本表安装实际程序。

### 求解器需要在 MatriCS 重新下载吗

MatriCS 需要有可运行的同版本求解器，但不要求所有程序重新下载，也不要求每批实验重新安装。先查看已有安装，版本和运行模式符合本次设置的直接复用。缺少的程序在首次部署时准备一次，之后由配置文件记录路径。

| 内容 | 首次部署方式 |
| --- | --- |
| NLIP 源码与实验脚本 | 从 GitHub 拉取 |
| Python 求解接口与依赖 | 在 MatriCS 的项目虚拟环境中按固定依赖文件安装，已有匹配环境可以复用 |
| WMaxCDCL、EvalMaxRes 和 nuwls | 可以传输对应官方发行包，也可以在 MatriCS 下载同一发行包；解包后在计算节点小测 |
| MaxHS、UWrMaxSAT 和 SCIP | 优先用相同源码版本在 MatriCS 编译并连接本站 SCIP 10.1.0；已有相同版本和模式的安装可以复用 |
| 独立 CaDiCaL 3.1.0 | 复用本站对应安装，或传输源码后在 MatriCS 编译 |
| Gurobi 许可证 | 使用计算节点可访问的有效许可证，安装 Python 包并不提供完整许可证 |

广州此次编译的 MaxHS、UWrMaxSAT 依赖 SCIP 及其动态库，程序还记录了广州的库搜索路径。只复制两个可执行文件并不能保证在 MatriCS 可用。需要连同兼容依赖正确部署，或在 MatriCS 按同一版本重新编译。具体版本、参数和模式以 [求解器版本说明](SOLVER_VERSIONS.md) 为准。

如果 MatriCS 无法访问下载站点，可以由广州下载源码或发行包后传过去；Python 依赖也可准备兼容目标 Python 和 Linux 的离线安装包。安装安排在首次部署阶段，正式 Slurm 作业只调用已准备好的程序，不在作业中下载或更新软件。后续步骤中的路径填写不会自动安装求解器。

### 4.3 安装 Python 环境

在登录节点安装。若 Python 由模块提供，先运行 `module avail python`，加载列表中实际存在的 3.12 模块。下方假定 `python3.12` 已可执行。

```bash
python3.12 --version
python3.12 -m venv .venv-solvers
export AIJ_PYTHON="$PWD/.venv-solvers/bin/python"
"$AIJ_PYTHON" -m pip install -r jobs/requirements.txt -r analysis/requirements-analysis.txt
"$AIJ_PYTHON" jobs/tools/check_environment.py
```

已有项目环境时跳过创建和安装，只设置 `AIJ_PYTHON` 并检查。成功时看到 `Python 依赖检查通过`。固定版本见依赖文件，Python 包和 SCIP 本体会分别核对。

如果 PySCIPOpt 版本正确，但 SCIP 本体不是 10.1.0，请提供 SCIP 安装的合作者协助连接到本站的 10.1.0。`SCIPOPTDIR` 下应有 `include/` 和包含 `libscip.so` 的 `lib/`。

```bash
export SCIPOPTDIR='/请填写/SCIP-10.1.0安装目录'
export LD_LIBRARY_PATH="$SCIPOPTDIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$AIJ_PYTHON" -m pip install --force-reinstall --no-deps --no-cache-dir --no-binary=pyscipopt 'pyscipopt==6.3.0'
"$AIJ_PYTHON" jobs/tools/check_environment.py
```

自定义 SCIP 连接方式见 [PySCIPOpt 官方源码安装说明](https://pyscipopt.readthedocs.io/en/latest/build.html)。需要相应编译器和 Python 开发头文件，由站点环境提供。提交时保留所需模块和动态库环境，提交脚本会把当前环境传到计算节点。

若当前检查提示 SCIP 本体版本不匹配，先按下一节准备 SCIP 10.1.0，再回到上一段重新连接 PySCIPOpt 并检查。

### 4.4 准备外部求解器

外部程序首次部署一次，之后复用。该步骤需要能编译 Linux 软件的人完成，合作者可与管理员共同操作。先查看本站已有版本，缺少的才安装。源码或发行包可以从广州传到 MatriCS，也可以由 MatriCS 下载；不要复制广州整个虚拟环境。

可将本站软件集中放在 `$HOME/software/nlip-20261124/`，该位置必须能被计算节点读取。以下示例仅创建目录，不安装软件。

```bash
mkdir -p "$HOME/software/nlip-20261124/src"
mkdir -p "$HOME/software/nlip-20261124/bin"
export NLIP_SOFTWARE="$HOME/software/nlip-20261124"
```

| 程序 | 安装要求 | 安装后要取得的文件 |
| --- | --- | --- |
| SCIP 10.1.0 | 复用模块或安装该版本，保留 C/C++ 头文件及库；PySCIPOpt、MaxHS、UWrMaxSAT 均须连接正确版本 | SCIP 安装根目录、`include/`、`lib/` 或 `lib64/` |
| MaxHS | 固定到第 2 部分的 ASchidler 提交；CMake 3.28 或更新，C++17 编译器，Release，启用 SCIP | `maxhs` |
| UWrMaxSAT | v2.0.6，启用 MaxPre 和 SCIP 10.1.0，CaDiCaL 内部依赖按原构建保留 | `uwrmaxsat` |
| WMaxCDCL | 官方 `solver-WMaxCDCL2026.zip` 中的独立版 | `wmaxcdcl_static` |
| EvalMaxRes | 官方 `solver-EvalMaxRes.zip`，保留包内辅助程序 | `EvalMaxSAT` 和 `nuwls` |
| CaDiCaL | 独立 v3.1.0，Release 默认构建 | `cadical` |

官方下载入口见第 2.1 节。UWr 的构建细节见 [上游说明](https://github.com/marekpiotrow/UWrMaxSat/tree/v2.0.6)，MaxHS 见 [固定提交](https://github.com/ASchidler/MaxHS/tree/b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740)。不要照抄上游示例中的旧 SCIP 10.0.3 来替代本批 10.1.0。

广州已保留本次使用的第三方源码和编译配置。需要离线部署或复现嵌入依赖时，从广州 `ROOT/solvers/20261124/` 取得源码压缩包，并参考 `/home/ubuntu/nlip-solver-build-20261124/uwrmaxsat/config.mk` 和对应编译日志。MaxPre、COMiniSatPS 等内部依赖应复用这批归档源码，避免重新下载移动中的 master 分支。

独立 CaDiCaL 的源码安装示例为以下命令。`make -j2` 使用两个编译进程；登录节点不允许编译时，按本站要求申请交互计算节点后执行。

```bash
cd "$NLIP_SOFTWARE/src"
git clone --branch rel-3.1.0 --depth 1 https://github.com/arminbiere/cadical.git cadical-3.1.0
cd cadical-3.1.0
./configure
make -j2
cp build/cadical "$NLIP_SOFTWARE/bin/cadical"
"$NLIP_SOFTWARE/bin/cadical" --version
```

MaxHS 的构建示例在已经准备好 SCIP、GMP、MPFR 头文件和库之后执行。`SCIP_INCLUDE_DIR` 和 `SCIP_LIBRARY_DIR` 必须填入本站实际路径。

```bash
export SCIP_INCLUDE_DIR='/请填写/SCIP-10.1.0/include'
export SCIP_LIBRARY_DIR='/请填写/SCIP-10.1.0/lib或lib64'
cd "$NLIP_SOFTWARE/src"
git clone https://github.com/ASchidler/MaxHS.git maxhs
cd maxhs
git checkout b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DUSE_SCIP=ON   -DSCIP_INCLUDE="$SCIP_INCLUDE_DIR" -DSCIP_LIB="$SCIP_LIBRARY_DIR"
cmake --build build --parallel 2
find build -type f -name maxhs -perm -u+x
```

最后一条列出实际生成的程序，将其复制到本站软件的 `bin/` 目录，或直接把该绝对路径填入后续配置。CMake 若提示找不到 GMP 或 MPFR，应加载相应开发模块或填写上游支持的 include/lib 参数。

UWrMaxSAT 使用相邻的 `cominisatps/`、`cadical/`、`maxpre/` 依赖目录。按上游顺序准备归档依赖，内部 CaDiCaL 3.0.0 应用 UWr 附带补丁，编译 CaDiCaL 和 MaxPre；复制 `config.cadical` 为 `config.mk`，将 SCIP include/library 路径改为本站 10.1.0，再执行 `make r`。共享库构建方式可使用 `make r LDFLAG_STATIC=`，同时配置实际库搜索路径。广州的 `libmpfr.so.4` 是其本机 SCIP 配套库名，不能假定 MatriCS 也使用该名称，必须与本站 SCIP 二进制兼容。产物为 `build/release/bin/uwrmaxsat`。

程序准备后，使用 `ldd /实际程序路径` 查看动态依赖，若出现 `not found`，先加载正确模块或补齐库。静态程序可能显示“not a dynamic executable”，这本身不表示错误。回到项目目录继续后续步骤。

```bash
cd /scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-
unset UWRFLAGS
```

### 4.5 准备实例数据

GitHub 提供实例清单，不包含全部原始数据。优先复用 MatriCS 已有 benchmark 目录，确保四份清单中每个名称都能唯一找到。QPLIB 137 个，DiverseSAT 108 个，有界 SMT 150 个，MIPO 870 个 JSON。

如果缺少数据，由广州把对应目录传到 MatriCS 共享存储后再填写路径。MIPO 使用已经转换且与清单一致的 870 个 JSON，不在重跑时重新生成另一组随机输入。数据不齐时配置工具会报告具体缺失名称，补齐后继续。

### 4.6 填写本站路径、版本和参数

从项目根目录执行，将以下路径替换成上述部署取得的真实位置。数据根目录下应包含 `qplib_fully_passed` 和 `smt_0_10` 等子目录。

```bash
export NLIP_BENCHMARK_ROOT='/请填写/benchmarks'
export NLIP_DIVERSE_ROOT='/请填写/diverse_sat'
export NLIP_MIPO_ROOT='/请填写/870个MIPO-JSON所在目录'
export NLIP_MAXHS='/请填写/maxhs'
export NLIP_WMAXCDCL='/请填写/wmaxcdcl_static'
export NLIP_UWRMAXSAT='/请填写/uwrmaxsat'
export NLIP_EVALMAXRES='/请填写/EvalMaxSAT'
export NLIP_EVALMAXRES_HELPER='/请填写/nuwls'
export NLIP_CADICAL='/请填写/cadical-3.1.0'
"$AIJ_PYTHON" jobs/tools/configure_cluster.py
```

成功时显示 `runs: 22220`，其中 QPLIB 2192、DiverseSAT 1728、MIPO 17400、SMT 900。生成的 `jobs/config.cluster.json` 留在 MatriCS，不提交 GitHub，不用广州同名文件覆盖。

若报 `expected one input, found 0`，检查数据路径并补齐对应文件。MIPO 使用已经转换的同一批 JSON，不通过改清单跳过缺失输入。

接着打开配置文件。

```bash
nano jobs/config.cluster.json
```

找到 `solver_metadata`，按下列结构填入五个外部后端的实际信息。下面是本批选定版本的字段示例。先确认实际安装与该表一致，再填写；插入现有 JSON 时保留相邻字段所需的逗号。

```json
"solver_metadata": {
  "MAXHS": {"release": "ASchidler/MaxHS b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740", "mode": "SCIP 10.1.0; -no-lp-harden-reduced"},
  "WMAXCDCL": {"release": "MSE2026 WMaxCDCL2026", "mode": "standalone"},
  "UWRMAXSAT": {"release": "UWrMaxSat v2.0.6", "mode": "MaxPre; SCIP 10.1.0 sequential; -no-par"},
  "EVALMAXRES": {"release": "MSE2026 EvalMaxRes", "mode": "exact; nuwls helper"},
  "CADICAL": {"release": "CaDiCaL 3.1.0", "mode": "standalone sequential SAT"}
}
```

按 `Ctrl+O`、回车保存，`Ctrl+X` 退出。下面的检查成功时无输出。

```bash
"$AIJ_PYTHON" -m json.tool jobs/config.cluster.json > /dev/null
```

`external_solver_args` 保存实际启动参数。工具预填广州已验证的 UWrMaxSAT 2.0.6、MSE2026 EvalMaxRes 和 MaxHS SCIP 模式参数。MaxHS 直接调用二进制，并显式传入 `-optimizer=scip -no-lp-harden-reduced`。更换发行版时核对参数兼容性，模式描述必须与实际命令一致。

### 4.7 计算节点环境与许可证

先用短作业确认计算节点也能加载依赖。命令可能等待资源，获得资源后会打印结果。

```bash
srun --partition=bigmem-amd --nodes=1 --ntasks=1 --cpus-per-task=1 --mem=2G --time=00:05:00 \
  "$AIJ_PYTHON" jobs/tools/check_environment.py
```

再检查 Gurobi 完整许可证。模型超过受限许可证变量规模，求解上限两秒。

```bash
srun --partition=bigmem-amd --nodes=1 --ntasks=1 --cpus-per-task=1 --mem=2G --time=00:05:00 \
  "$AIJ_PYTHON" - <<'PY'
import gurobipy as gp
with gp.Env(params={'OutputFlag': 0}) as env, gp.Model(env=env) as model:
    model.Params.Threads = 1
    model.Params.TimeLimit = 2
    x = model.addVars(2001, vtype=gp.GRB.BINARY)
    model.addConstr(x.sum() <= 1)
    model.setObjective(x.sum(), gp.GRB.MAXIMIZE)
    model.optimize()
print('Gurobi full-size license check passed')
PY
```

成功时看到 `Gurobi full-size license check passed`。若出现 `Model too large for size-limited license`，由合作者配置完整许可证后重试。

### 4.8 提交 58 配置小测

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py --profile smoke --output results/smoke-new-solvers
bash results/smoke-new-solvers/submit.sh
```

第一条只生成计划，预期 `configuration_jobs: 58`、`instance_runs: 58`、`workers: 1`。第二条提交作业，打印并保存数组编号与分析编号。每个小测元素申请五分钟，结束后自动汇总。

```bash
squeue --me
sacct -j "$(cat results/smoke-new-solvers/array_job_id.txt)" --format=JobID,State,ExitCode,Elapsed
sacct -j "$(cat results/smoke-new-solvers/analysis_job_id.txt)" --format=JobID,State,ExitCode,Elapsed
```

`PENDING` 是排队，`RUNNING` 是运行，`COMPLETED` 是作业正常退出。数组和分析都结束后检查汇总。

```bash
cat results/smoke-new-solvers/summary.json
```

应有 58 条结果，`OPTIMAL: 52`、`SAT: 6`。每个配置日志还应有 `Tests passed: 1`，表示已核对已知答案和原问题验解。日志在 `results/smoke-new-solvers/slurm-*.log`。有缺失或失败时先看对应日志，再提交正式实验。

### 4.9 提交正式主批

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py --output results/main-new-solvers
```

核对输出后再提交。

```text
configuration_jobs   58
instance_runs        22220
workers              60
concurrent_jobs      1
memory_gib           970
```

每实例一个物理核、16 GiB，启动至求解结束 3600 秒，验解另给 120 秒，外围上限 4000 秒。每配置申请一个独占 bigmem-amd 节点、60 核、970 GiB。按最大配置 870 个输入估算，作业申请 19 小时。若站点配额不允许，先与负责人确定资源修改，再重新生成计划。

```bash
bash results/main-new-solvers/submit.sh
squeue --me
```

提交脚本检查版本和配置，提交含 58 个元素的数组及依赖数组结束的分析作业，并保存编号。它拒绝直接重复提交同一批次。运行期间保留这个 checkout 的代码、配置和二进制版本，等本批结束再更新。

### 4.10 查看进度和结果

```bash
sacct -j "$(cat results/main-new-solvers/array_job_id.txt)" --format=JobID,State,ExitCode,Elapsed
sacct -j "$(cat results/main-new-solvers/analysis_job_id.txt)" --format=JobID,State,ExitCode,Elapsed
cat results/main-new-solvers/summary.json
```

| 文件或目录 | 内容 |
| --- | --- |
| `campaign.json` | 实例、方法和资源计划 |
| `summary.json` | 应运行数及状态计数 |
| `results.csv` | 每次求解的完整汇总 |
| `analysis/config_summary.csv` | 每配置的完成数、解出数和时间 |
| `analysis/` | 统计表和图 |
| `sumup/` | 与旧格式衔接的表格 |
| `runs/` | 原始结果、日志及验解信息 |

正式实验结束要求计划的 22,220 条均有终态记录，不要求全部 OPTIMAL。TIMEOUT、OOM、UNSUPPORTED、LICENSE_LIMIT、ERROR 等保留。`PENDING` 表示尚无终态记录，应查对应作业。

分析作业单独失败时，重新汇总已有结果，不重新求解。

```bash
srun --partition=normal --nodes=1 --ntasks=1 --cpus-per-task=1 --mem=4G --time=00:30:00 \
  "$AIJ_PYTHON" analysis/analyze_campaign.py results/main-new-solvers
```

数组被取消或某元素失败时，把数组编号、元素编号和对应日志交给负责人，确定重排范围。运行器支持同版本同配置续跑并保留已完成记录。不要删除结果或重复提交整批来处理局部失败。

### 4.11 下次登录

重新加载首次部署使用的 Python、编译器或 SCIP 模块和动态库环境，再进入项目目录。

```bash
cd /scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-
export AIJ_PYTHON="$PWD/.venv-solvers/bin/python"
unset UWRFLAGS
"$AIJ_PYTHON" jobs/tools/check_environment.py
```

程序和数据路径已保存在 `jobs/config.cluster.json`，无需重新安装或填写。若需要 `LD_LIBRARY_PATH` 或许可证环境变量，每次提交前仍要恢复它们；Slurm 提交脚本传递当前环境。

## 5. 修改配置、消融、恢复与交付

### 5.1 到哪里改

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

### 5.2 选择分区与并行数

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

### 5.3 修改路径和参数的例子

修改可逆的本站设置时，编辑 `jobs/config.cluster.json`，保留源码和实例清单。也可以用以下方式修改某个字段，避免手工 JSON 逗号错误。先将路径替换成实际安装。

```bash
"$AIJ_PYTHON" - <<'PY'
import json
from pathlib import Path
p = Path('jobs/config.cluster.json')
c = json.loads(p.read_text())
c['solver_paths']['UWRMAXSAT'] = '/请填写/uwrmaxsat实际可执行文件'
c['solver_metadata']['UWRMAXSAT'] = {
    'release': 'UWrMaxSat v2.0.6',
    'mode': 'MaxPre; SCIP 10.1.0 sequential; -no-par'
}
p.write_text(json.dumps(c, indent=2) + '\n')
PY
```

仅修改版本文字不会升级程序。更换求解器时需要安装新程序、修改实际路径、核对启动参数，然后重跑小测；正式性能结果使用新的批次目录。配置工具现在对显式给出的错误求解器路径直接报错，不再回退使用旧程序。

日常修改资源优先使用生成器参数，例如 `--partition bigmem --workers 28 --concurrent-jobs 1`。修改时间或每实例内存时编辑 `profiles.formal`。生成器会按 worker 数检查总内存是否足够，并估算作业最长时间。正式批次开始后保持预算固定。

实验组合由 `jobs/internal/experiment.py` 的 `methods()` 定义，数据族和清单由 `jobs/config.json` 与本站配置定义。改变它们属于改变实验方案，应更新本手册并重新生成计划；不要为缺失或困难实例临时删减冻结清单。

### 5.4 独立共享消融

先完成相同平台下的主批，以其中 BIN+D 共享配置为配对基准。另生成关闭共享的 1,020 次调用。

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py --matrix decomposition   --output results/decomposition-new-solvers
bash results/decomposition-new-solvers/submit.sh
```

预期为 2 个配置和 1,020 次运行，MIPO 870、有界 SMT 150。合并比较时保持求解器、机器、时间预算一致。

### 5.5 中断或失败后如何处理

1. 用 `sacct` 和对应日志区分排队、资源中断、许可证失败及模型错误。
2. 分析作业失败时，只重跑 `analysis/analyze_campaign.py`，无需重新求解。
3. 数组元素因外部原因中断时，运行器支持保留已完成记录并继续剩余实例。先确认原数组不再运行，代码、配置和程序未变化，再处理该元素。
4. `TIMEOUT` 和 `OOM` 是正式终态，续跑不会自动覆盖。代码或预算改变后重新实验，应另开结果批次。

同一批次、同一配置恢复的操作示例为重新排队原数组元素。将 `数组编号_元素编号` 换成 `array_job_id.txt` 和日志对应值，实际是否允许由本站 Slurm 配置决定。

```bash
scontrol requeue 数组编号_元素编号
```

原自动分析作业若已经结束，恢复任务结束后按第 4.10 节重新汇总。若本站不允许 requeue，把对应日志交给负责人安排指定元素，不删除原结果目录。

### 5.6 保存和交付结果

先确认 `summary.json` 的 planned 为 22,220、没有 PENDING，并检查 ERROR、INVALID、LICENSE_LIMIT 等状态的原因。完整原始结果保留在 `results/<批次>/runs/`。不要只保留成功记录或图表。

可选工具可导出精简交付，不会自动推送。

```bash
bash analysis/push_results.sh export main-new-solvers
```

输出位于 `deliveries/main-new-solvers/`，验解记录包留在原批次目录。负责人审核结果后再决定是否运行该工具的 `push` 操作。这里的结果交付与当前源码同步分开。

## 6. 交付验证与当前限制

本次检查覆盖编码与预处理改动、正式方法矩阵、外部状态和模型读取、Python 基线、预算与进程树清理、Slurm 调用、续跑和结果统计。最终验证在广州准备发布的源码副本上执行。

本次最终交付副本验证结果如下。

| 验证内容 | 结果 |
| --- | --- |
| 实验运行、后端、配置与分析回归 | 43 项通过 |
| 核心编码、预处理与接口回归 | 50 项通过 |
| 公共 API 脚本 | 56/56 通过 |
| 58 配置经实际 Slurm 执行模板运行 | 52 OPTIMAL、6 SAT，全部已知答案与原问题验解通过 |
| 汇总与绘图 | 完成，58 条结果与计划一致 |
| 生成的提交脚本 | 本地模拟验证数组参数、分析依赖、编号保存和重复提交拒绝 |
| 正式与消融计划 | 主批 58 / 22,220；消融 2 / 1,020；bigmem 备选为 28 worker / 450 GiB |
| DiverseSAT 配置位置统一 | 170 个实验作业及 13 个辅助提交脚本与调整前内容一致，实际消费者加载通过 |

广州记录位于 `ROOT/results/github-delivery-20261124/`。这些日志留在本机，测试源代码随仓库交付。58 配置使用四个已知答案的小模型，覆盖全部正式方法组合。MatriCS 正式性能作业尚未提交。广州 Gurobi 当前许可证规模受限，MatriCS 正式运行前必须通过完整规模许可证探针和 58 配置计算节点小测。UNSAT 目前记录后端终态，未对每个实例增加独立不可满足证明检查。正式论文结论还需对最终运行结果完成原问题验解与可用公开参考值核对。
