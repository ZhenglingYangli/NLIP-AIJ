# NLIP-AIJ 实验与 MatriCS 操作手册

更新于 2026-11-24。内容依次为实验方案、求解器设置、文件结构、安装运行和配置修改。首次接手从第 4 部分开始操作，第 1 至 3 部分用于查阅。

除上传文件外，命令均在 MatriCS 终端执行。【必改】字段以及 `CHANGE_ME`、`USER@HOST` 必须替换成实际值。

## 1. 实验方案与配置

### 1.1 正式主批

| 数据族 | 输入数 | 编码及后端 | 直接建模基线 | 配置数 | 运行数 |
| --- | ---: | --- | --- | ---: | ---: |
| QPLIB | 137 | OH、UNA、BIN × MaxHS、WMaxCDCL、UWrMaxSAT、EvalMaxRes | SCIP-native、Z3、CP-SAT、Gurobi | 16 | 2,192 |
| DiverseSAT 应用模型，k=2 | 108 | 同上 | 同上 | 16 | 1,728 |
| MIPO | 870 | OH、UNA、BIN、BIN+D × 上述四后端 | 同上 | 20 | 17,400 |
| 有界 SMT | 150 | OH、UNA、BIN、BIN+D × CaDiCaL | Z3、cvc5 | 6 | 900 |
| 合计 | 1,265 | | | 58 | 22,220 |

SCIP、Gurobi 和 CP-SAT 直接建模有界整数多项式，cvc5 用于 SMT 判定。BIN+D 的分解设置见 1.4 节。

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

小测每个配置只有一个输入，使用一个工作进程，每个 Slurm 元素申请五分钟。

### 1.3 执行和验解

生成器读取清单并生成作业。Slurm 分配资源后，运行器解析、编码或建模、调用求解器，并对返回的赋值检查原始约束和目标。每个实例保存 `result.json`，整批汇总为 `results.csv`，统计表和图保存在 `analysis/`。

### 1.4 正式统计口径

优化任务只有 `OPTIMAL` 且原问题验解通过才计入“解出”。只有可行解时记为 `FEASIBLE`，不会计为已证明最优。SMT 的 `SAT` 必须有验解通过的赋值；`UNSAT` 记录求解器终态，不附独立不可满足证明。`TIMEOUT`、`OOM`、`UNSUPPORTED`、`LICENSE_LIMIT`、`ERROR`、`INVALID` 分开保留。`PENDING` 表示尚无终态记录。

论文分析时间使用 `solve_wall_seconds`，包含启动、解析、建模或编码以及求解。原问题验解时间单独记录。完整配置的 PAR-2 将未成功的运行按两倍求解预算计入；仍有 PENDING 的配置暂不计算 PAR-2。小测时间不作为论文性能结果。

主批分解方法 BIN+D 使用阈值 3、顺序分解、精确乘法和子结构共享。共享消融仅将 `decomp_shared` 改为 false，保持其余设置相同。主批和消融均关闭 LRN。

## 2. 求解器版本、程序与运行方式

使用下列固定版本，同一批次运行期间保持版本和参数不变。

### 2.1 版本与来源

| 求解器或接口 | 固定版本 | 下载来源 |
| --- | --- | --- |
| UWrMaxSAT | 2.0.6 | [正式发布 v2.0.6](https://github.com/marekpiotrow/UWrMaxSat/releases/tag/v2.0.6)，2026-08-06 |
| MaxHS | 修订版 ASchidler/MaxHS，提交 `b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740` | [维护仓库的对应源码](https://github.com/ASchidler/MaxHS/commit/b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740) |
| WMaxCDCL | MSE2026 独立版 | [官方 2026 求解器发布包](https://zenodo.org/records/21358014)，`solver-WMaxCDCL2026.zip` |
| EvalMaxRes | MSE2026 发布版 | [官方 2026 求解器发布包](https://zenodo.org/records/21358014)，`solver-EvalMaxRes.zip` |
| CaDiCaL，用于正式 SMT 编码 | 3.1.0 | [正式发布 rel-3.1.0](https://github.com/arminbiere/cadical/releases/tag/rel-3.1.0)，2026-11-17 |
| SCIP | 10.1.0 | [正式发布 v10.1.0](https://github.com/scipopt/scip/releases/tag/v10.1.0) |
| PySCIPOpt | 6.3.0 | [官方 PyPI 包](https://pypi.org/project/PySCIPOpt/) |
| Z3 | 5.4.1.0 | [官方 PyPI 包](https://pypi.org/project/z3-solver/) |
| OR-Tools / CP-SAT | 9.15.6755 | [官方 PyPI 包](https://pypi.org/project/ortools/) |
| Gurobi | 14.0.0 | [官方 PyPI 包](https://pypi.org/project/gurobipy/) |
| cvc5 | 1.4.2 | [官方 PyPI 包](https://pypi.org/project/cvc5/) |
| PySAT | 1.9.dev24 | [官方 PyPI 包](https://pypi.org/project/python-sat/) |

MaxHS 使用指定提交，WMaxCDCL 使用独立版。EvalMaxRes 包内程序名为 `EvalMaxSAT`，下载时选择 `solver-EvalMaxRes.zip`。

### 2.2 实际程序位置

按第 4 部分安装后，`NLIP_SOFTWARE` 为 `$NLIP_PROJECT/solvers/matrics-20261124`。复用已有安装时，在 `matrics.env` 中修改对应路径。

| 配置键 | 实际程序路径 |
| --- | --- |
| `MAXHS` | `$NLIP_SOFTWARE/bin/maxhs` |
| `WMAXCDCL` | `$NLIP_SOFTWARE/bin/wmaxcdcl_static` |
| `UWRMAXSAT` | `$NLIP_SOFTWARE/bin/uwrmaxsat` |
| `EVALMAXRES` | `$NLIP_SOFTWARE/bin/EvalMaxSAT` |
| EvalMaxRes 辅助程序 | `$NLIP_SOFTWARE/bin/nuwls` |
| `CADICAL` | `$NLIP_SOFTWARE/bin/cadical` |
| SCIP 共享库 | `$SCIP_LIBRARY_DIR/libscip.so` |
| Python 解释器 | `$NLIP_PROJECT/.venv-solvers/bin/python` |

程序路径写入 `jobs/config.cluster.json` 的 `solver_paths`，启动参数写入 `external_solver_args`。Python 基线由上述解释器导入对应模块运行。

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

保持 `UWRFLAGS` 未设置，避免覆盖命令行参数。

UWrMaxSAT 和 MaxHS 的内部 CaDiCaL 使用各自固定依赖。正式 SMT 单独调用 CaDiCaL 3.1.0，两者分开安装。

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

### 2.4 Python 基线和资源设置

| 基线 | 模式及主要参数 |
| --- | --- |
| SCIP-native | 整数多项式直接建模；`parallel/maxnthreads=1`，`randomization/randomseedshift=0`，`numerics/feastol=1e-9`，`limits/gap=0`，`limits/absgap=0`，`limits/time` 为剩余预算 |
| CP-SAT | 整数变量和乘积约束，目标和约束的有理系数做精确整数缩放；`num_search_workers=1`，`random_seed=0`，`max_time_in_seconds` 为剩余预算 |
| Gurobi | 有界整数多项式及乘积辅助变量；`Threads=1`，`Seed=0`，`NonConvex=2`，`MIPGap=0`，`MIPGapAbs=0`，`FeasibilityTol=1e-9`，`IntFeasTol=1e-9`，`TimeLimit` 为剩余预算 |
| Z3 | 保留现有优化与判定流程；优化使用 Optimize 及后续已实现的证明/改进检查，SMT 使用现有 solver 路线；每阶段 timeout 使用剩余预算 |
| cvc5 | 仅 SMT 判定；`produce-models=true`，`incremental=true`，`seed=0`，`tlimit-per` 为剩余毫秒 |

所有 worker 绑定一个物理核。可行解回到原问题验解，并重新计算原始目标。UNSAT 记录后端终态，没有为每个实例增加独立 UNSAT 证明检查。

Python 主环境为 3.12。固定依赖为 `python-sat[pb]==1.9.dev24`、`pindakaas==0.6.1`、`z3-solver==5.4.1.0`、`psutil==7.2.2`、`pyscipopt==6.3.0`、`numpy==2.5.4`、`cvc5==1.4.2`、`ortools==9.15.6755`、`gurobipy==14.0.0`，绘图使用 `matplotlib==3.9.4`。

Python 基线通过 `jobs/config.cluster.json` 的 `python` 启动，每个实例的入口为 `jobs/internal/worker.py <job.json>`。它导入对应 Python 接口，不另行调用 `z3`、`gurobi_cl` 或 `scip` 命令行程序。实际解释器和外部命令分别记录在 `result.json` 的 `command` 和 `external_command` 中。环境与版本记录在各配置的 `run.json` 中。

## 3. 代码位置、文件结构与职责

### 3.1 项目位置与入口

源码仓库为 [NLIP-Journal-Artifact-](https://github.com/ZhenglingYangli/NLIP-Journal-Artifact-)。项目目录由 `NLIP_PROJECT` 指定，代码、配置、数据和程序必须能被计算节点访问。

- `jobs/generate_scripts.py` 生成作业。
- `jobs/goSolver.py` 运行实例。
- `jobs/internal/experiment.py` 定义实验组合。

### 3.2 文件结构

```text
项目根目录/
├── README.md                    项目入口
├── MATRICS_GUIDE.md             完整安装与实验手册
├── matrics.env.example          本站环境配置模板
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
│   │   ├── runner.py             并行调度、CPU 分配、结果保存与续跑
│   │   ├── supervisor.py         监督进程树的时间、内存和终止
│   │   └── worker.py             读取一个任务，调用求解器并验解
│   ├── tools/                   首次配置、环境检查、输入检查
│   └── data/                    MIPO 数据准备与转换工具
├── codes/
│   ├── main.py                 单模型命令行入口
│   ├── tools/             输入解析、预处理、精确算术和验解
│   ├── encoders/           OH、UNA、BIN 与分解编码
│   ├── solver/             SAT/MaxSAT 调用、终态与模型读取
│   ├── nlipsat/                 对外 Python API
│   ├── baselines/         SCIP、Z3、CP-SAT、Gurobi、cvc5 适配
│   └── tests/                   求解核心与接口测试
├── benchmarks/manifests/        正式实例清单
├── analysis/                    汇总、统计表、图和结果导出
├── tests/                       实验运行、资源限制和统计测试
└── results/                     本机产生的日志和结果，不进源码提交
```

Python 环境、外部求解器二进制、许可证和原始数据留在各自机器上。日常操作只使用两个实验入口。`codes/` 直接包含求解入口、编码器、解析工具、基线和 Python API。

### 3.3 主要文件功能

| 文件 | 功能和修改时机 |
| --- | --- |
| `jobs/generate_scripts.py` | 检查依赖和输入，生成任务计划与提交命令；默认分区、并行数在顶部，日常优先用命令行参数覆盖 |
| `jobs/goSolver.py` | 小测、单配置执行和 Slurm 数组入口，核对计划与续跑条件 |
| `jobs/internal/experiment.py` | 方法组合、配置读取、实例展开、任务编号；修改科研方案时才改 |
| `jobs/internal/runner.py` | 并行分发、物理核绑定、环境记录、结果保存与续跑 |
| `jobs/internal/supervisor.py` | 进程树时间和内存控制、终止清理、阶段计时 |
| `jobs/internal/worker.py` | 解析单个任务、调用编码或基线、验解并输出结果 |
| `jobs/internal/run_slurm.sh` | 计算节点执行模板，由生成的提交脚本调用 |
| `jobs/config.json` | 新机器的配置起点，随 GitHub 交付 |
| `jobs/config.cluster.json` | 本站路径、程序、参数、预算及版本，不提交 GitHub |
| `jobs/requirements*.txt` | 正式实验的固定 Python 依赖 |
| `jobs/tools/configure_cluster.py` | 将环境变量和已有路径写入本站配置，检查正式输入是否齐全 |
| `jobs/tools/check_environment.py` | 检查 Python 包版本、可导入性及 SCIP 本体版本 |
| `jobs/tools/check_final_inputs.py` | 检查输入清单，解析多项式数据；不运行正式性能实验 |
| `jobs/data/prepare_mipo.py`、`convert_mipo.py` | MIPO 数据准备与 JSON 转换；正式重跑复用已冻结的 870 个 JSON |
| `benchmarks/manifests/*.txt` | 四个正式实例清单；SMT 主批使用 `smt_list_small.txt` |
| `codes/encoders/onehot.py`、`unary.py`、`binary.py` | OH、UNA、BIN 编码 |
| `codes/encoders/constraints.py`、`decomposition.py`、`encoder_driver.py` | 约束编码、乘积分解、编码调度 |
| `codes/tools/*_parser.py`、`dimacs.py` | QPLIB、CNF/DiverseSAT 和 SMT 输入解析 |
| `codes/tools/preprocessing.py`、`arithmetic.py`、`verify.py` | 预处理、精确算术与目标恢复、原问题验解 |
| `codes/solver/config.py` | 编码选项和 BIN+D 预设；正式方法选择仍由实验配置模块控制 |
| `codes/solver/solve.py`、`sat.py` | MaxSAT、SAT 调用以及状态与模型读取 |
| `codes/baselines/` | SCIP、Z3、CP-SAT、Gurobi 和 cvc5 等适配，部分历史基线保留作开发用途 |
| `codes/nlipsat/` | Python API 与命令行包入口 |
| `codes/telemetry.py` | 运行阶段、模型规模和求解质量记录 |
| `analysis/summarize.py` | 单配置与整批结果汇总，保留失败和缺失项 |
| `analysis/analyze_campaign.py`、`run_campaign_analysis.sh` | 配置统计、成对比较、曲线图和分析作业 |
| `analysis/export_results.py`、`push_results.sh` | 可选结果交付工具；原始结果另行保留 |
| `tests/test_*.py`、`codes/tests/` | 可复用回归测试，验证接口、语义、资源控制和统计；不是正式性能输入 |
| `jobs/smoke/` | 四个已知答案的小模型，组合成 58 配置小测 |

### 3.4 本机文件

GitHub 提供源码、配置模板、依赖文件、实例清单和小测输入。`matrics.env`、`jobs/config.cluster.json`、求解器、虚拟环境、许可证、完整数据和运行结果保存在本机。

## 4. 合作者从零开始在 MatriCS 运行

### 4.1 先填写本站信息，再取得源码

本节采用以下标记。

- **【必改】** 与账户有关，必须替换。`CHANGE_ME` 是占位符，不能原样执行。
- **【条件修改】** 已有符合版本的安装或站点配置时才修改。
- **【直接运行】** 完成前面的填写和检查后，按原文执行。
- **【需要管理员】** 依赖账户权限或集群软件环境，本手册不能替账户提供。

**【必改，自己的电脑】** 将下方 `USER@HOST` 替换成管理员提供的 MatriCS 登录地址，然后登录。若使用机构 VPN、跳板机或特定 SSH 端口，沿用账户已有的登录方式。

```bash
ssh USER@HOST
```

**【必改，MatriCS 登录节点】** 只修改下面第一行的账户共享目录。本例沿用合作者 scherif 的路径；其他账户改成其计算节点可见、具有写权限的路径。路径不要包含空格。

```bash
export NLIP_PROJECT='/scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-'
mkdir -p "$(dirname "$NLIP_PROJECT")"
git clone https://github.com/ZhenglingYangli/NLIP-Journal-Artifact-.git "$NLIP_PROJECT"
cd "$NLIP_PROJECT"
git log -1 --oneline
ls jobs/generate_scripts.py jobs/goSolver.py jobs/internal/experiment.py
```

已有这个目录时，不重复 clone。先确认本目录没有正在运行的实验，再 `cd "$NLIP_PROJECT"`，检查 `git status --short`，执行 `git pull --ff-only`。源码有修改或不能快进时保留现场，交给负责人处理。

### 4.2 一次填写路径和模块，后续登录直接恢复

先查看本站可用模块，按实际名称填写。

```bash
module avail python
module avail gcc
module avail cmake
module avail scip
```

**【需要管理员】** 准备 Python 3.12 及开发头文件、支持 C++17 的 GCC/G++、make、patch、curl、tar、GMP 和 zlib 开发头文件。CMake 将在项目虚拟环境安装，无需先有系统 CMake。缺少模块或头文件时，请管理员提供或加载相应模块；不用在集群盲目运行 `sudo apt install`。

需要填写的内容集中在下面这些字段。后面的程序下载地址、版本号和编译参数保持原文。

| 字段 | 必须填写或核对的值 | 什么时候需要改 |
| --- | --- | --- |
| 登录命令的 `USER@HOST` | 自己的 MatriCS SSH 地址 | 必改 |
| `module load ...` | 本站实际 Python、编译器和开发库模块 | 软件通过模块提供时必改；已由系统提供则保留注释 |
| `NLIP_PROJECT` | 计算节点可见的项目绝对路径 | 必须与 4.1 一致 |
| `NLIP_BOOTSTRAP_PYTHON` | 加载模块后的 Python 3.12 命令或路径 | 必须核对，只有命令确实叫 python3.12 时才保留默认 |
| `NLIP_BENCHMARK_ROOT` | 同时包含 qplib_fully_passed 和 smt_0_10 的父目录 | 必改 |
| `NLIP_DIVERSE_ROOT` | 108 个 CNF 所在目录 | 必改 |
| `NLIP_MIPO_ROOT` | 870 个已转换 JSON 所在目录 | 必改 |
| `GRB_LICENSE_FILE` | 管理员提供的有效许可证文件 | 使用文件授权时取消注释并修改，其他授权方式按站点配置 |
| `SCIP_ROOT` | SCIP 10.1.0 根目录 | 复用已有安装时修改，按本文安装则保留默认 |
| 五个 `NLIP_求解器` 和辅助程序路径 | 实际可执行文件绝对路径 | 复用已有程序时修改，按本文安装则保留默认 |

**【直接运行，仅首次创建】** 创建本机环境文件。下面的命令仅在文件不存在时复制模板，保留已有设置。它不提交 GitHub，不是新的实验入口。

```bash
cd "$NLIP_PROJECT"
if [[ ! -e matrics.env ]]; then
  cp matrics.env.example matrics.env
fi
nano matrics.env
```

编辑后按 Ctrl+O、回车保存，Ctrl+X 退出。**模块命令、项目目录、Python 命令和三个数据目录必须由操作者确认。** 若数据尚未齐全，可先完成软件安装，到 4.6 前补齐。若复用已经安装的同版本求解器，将对应的 `NLIP_...` 指向它的实际程序，并跳过该求解器的安装段。

```bash
source matrics.env
"$NLIP_BOOTSTRAP_PYTHON" --version
g++ --version
make --version
command -v patch curl tar
"$NLIP_BOOTSTRAP_PYTHON" - <<'PY'
import sys, sysconfig
from pathlib import Path
assert sys.version_info[:2] == (3, 12), sys.version
header = Path(sysconfig.get_path('include')) / 'Python.h'
assert header.is_file(), f'Python 开发头文件缺失：{header}'
print('Python 3.12 和 Python.h 可用')
PY
printf '#include <gmp.h>\n#include <zlib.h>\nint main(){}\n' | g++ -x c++ -fsyntax-only -
```

最后一条成功时无输出。出现 `gmp.h`、`zlib.h` 或 `Python.h` 缺失，先补齐开发环境再编译。一次只执行一个代码块；任一块报错时，处理该错误后再继续。

### 4.3 下载和解包，准备 SCIP 与固定源码

**【直接运行】** 在共享存储建立软件目录。下载在能访问外网的登录节点进行，编译按本站政策在允许的节点执行。

```bash
mkdir -p "$NLIP_SOFTWARE/downloads" "$NLIP_SOFTWARE/src" "$NLIP_SOFTWARE/bin"
uname -m
getconf GNU_LIBC_VERSION
```

以下 SCIP 官方二进制包用于 `x86_64` 且 glibc 不低于 2.28 的 Linux。其他平台先让管理员提供 SCIP 10.1.0 安装，不能换成 ARM 包或随意降低版本。来源是 [SCIP 10.1.0 官方发布](https://github.com/scipopt/scip/releases/tag/v10.1.0)。

**【直接运行，首次安装 SCIP】**

```bash
(
set -e
cd "$NLIP_SOFTWARE/downloads"
curl --fail --location --retry 3 --connect-timeout 20 --max-time 1800 \
  -o scip-10.1.0-linux.tgz \
  'https://github.com/scipopt/scip/releases/download/v10.1.0/scipoptsuite-10.1.0-glibc2_28-amd64.tgz'
mkdir -p "$NLIP_SOFTWARE/scip"
tar -xzf scip-10.1.0-linux.tgz -C "$NLIP_SOFTWARE/scip" --strip-components=1
)
```

**【条件修改】** 如果管理员已提供 SCIP 10.1.0，则跳过上述下载，在 `matrics.env` 中把 `SCIP_ROOT` 改为其实际根目录，再执行 `source matrics.env`。目录必须同时有头文件和共享库。

```bash
if [[ -f "$SCIP_ROOT/lib/libscip.so" ]]; then
  export SCIP_LIBRARY_DIR="$SCIP_ROOT/lib"
else
  export SCIP_LIBRARY_DIR="$SCIP_ROOT/lib64"
fi
test -f "$SCIP_ROOT/include/scip/scip.h"
test -f "$SCIP_LIBRARY_DIR/libscip.so"
ldd "$SCIP_LIBRARY_DIR/libscip.so"
```

如果前两条 `test` 失败，检查解压目录或安装路径。`ldd` 若有 `not found`，先解决依赖。不要把整个第三方 `lib64` 盲目加入全局 `LD_LIBRARY_PATH`，以免覆盖 Python 使用的 C/C++ 运行库。下文把所需搜索路径写进新编译程序。

**【直接运行，下载固定源码】** 下面六个链接固定到实验要求的版本或提交。

```bash
(
set -e
cd "$NLIP_SOFTWARE/downloads"
while read -r filename url; do
  curl --fail --location --retry 3 --connect-timeout 20 --max-time 600 -o "$filename" "$url"
done <<'SOURCES'
uwr-2.0.6.tar.gz https://codeload.github.com/marekpiotrow/UWrMaxSat/tar.gz/refs/tags/v2.0.6
cominisatps.tar.gz https://codeload.github.com/marekpiotrow/cominisatps/tar.gz/f5a634f34eaefee40c043c2ca8062471b07650fa
cadical.tar.gz https://codeload.github.com/arminbiere/cadical/tar.gz/refs/tags/rel-3.0.0
maxpre.tar.gz https://codeload.github.com/Laakeri/maxpre/tar.gz/721f5dd129a7d50bda2d1b0d6729877ac1d3d768
MaxHS-latest.tar.gz https://codeload.github.com/ASchidler/MaxHS/tar.gz/b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740
cadical-latest.tar.gz https://codeload.github.com/arminbiere/cadical/tar.gz/refs/tags/rel-3.1.0
SOURCES
)
```

**【直接运行，解包源码】**

```bash
(
set -e
for name in uwrmaxsat cominisatps cadical maxpre maxhs cadical-3.1.0; do
  mkdir -p "$NLIP_SOFTWARE/src/$name"
done
cd "$NLIP_SOFTWARE/downloads"
tar -xzf uwr-2.0.6.tar.gz -C "$NLIP_SOFTWARE/src/uwrmaxsat" --strip-components=1
tar -xzf cominisatps.tar.gz -C "$NLIP_SOFTWARE/src/cominisatps" --strip-components=1
tar -xzf cadical.tar.gz -C "$NLIP_SOFTWARE/src/cadical" --strip-components=1
tar -xzf maxpre.tar.gz -C "$NLIP_SOFTWARE/src/maxpre" --strip-components=1
tar -xzf MaxHS-latest.tar.gz -C "$NLIP_SOFTWARE/src/maxhs" --strip-components=1
tar -xzf cadical-latest.tar.gz -C "$NLIP_SOFTWARE/src/cadical-3.1.0" --strip-components=1
)
```

归档中的 `MaxHS-latest.tar.gz` 实际固定到第 2 部分列出的提交，`cadical-latest.tar.gz` 固定为 3.1.0；这里的文件名不表示自动下载最新分支。不要在这个流程中重新获取移动中的 master。

**【直接运行，下载 WMaxCDCL 和 EvalMaxRes】** 下面是 [MSE2026 官方发行记录](https://zenodo.org/records/21358014) 中的准确文件。只下载这两个包，不下载全部 benchmark ZIP。

```bash
(
set -e
cd "$NLIP_SOFTWARE/downloads"
curl --fail --location --retry 3 --connect-timeout 20 --max-time 1800 \
  -o solver-WMaxCDCL2026.zip \
  'https://zenodo.org/api/records/21358014/files/solver-WMaxCDCL2026.zip/content'
curl --fail --location --retry 3 --connect-timeout 20 --max-time 1800 \
  -o solver-EvalMaxRes.zip \
  'https://zenodo.org/api/records/21358014/files/solver-EvalMaxRes.zip/content'
"$NLIP_BOOTSTRAP_PYTHON" - <<'PY'
import os, zipfile
from pathlib import Path
root = Path(os.environ['NLIP_SOFTWARE'])
for archive, members in [
    ('solver-WMaxCDCL2026.zip', ['WMaxCDCL2026/bin/wmaxcdcl_static']),
    ('solver-EvalMaxRes.zip', ['EvalMaxRes/bin/EvalMaxSAT', 'EvalMaxRes/bin/nuwls'])
]:
    with zipfile.ZipFile(root / 'downloads' / archive) as z:
        for member in members:
            target = root / 'bin' / Path(member).name
            target.write_bytes(z.read(member))
            target.chmod(0o755)
            print('已安装', target)
PY
)
```

WMaxCDCL 选择独立版 `wmaxcdcl_static`，不是 `wmaxcdcl_static_scip` 或组合启动器。EvalMaxRes 的程序名确实叫 `EvalMaxSAT`，辅助程序 `nuwls` 必须同时安装。若 MatriCS 下载失败，在能联网的机器下载同一链接并 `scp` 上传到 `$NLIP_SOFTWARE/downloads/`，再执行解包部分。出现 HTTP 错误时不要把错误页面当作 ZIP 解压。下载中断时可重试或在其他机器下载后上传；网络失败不需要改求解器版本。

### 4.4 创建 Python 环境并连接 SCIP

**【直接运行】** 新环境按固定依赖安装。已有本项目环境时可跳过第一行 venv 创建，但仍检查版本。

```bash
cd "$NLIP_PROJECT"
"$NLIP_BOOTSTRAP_PYTHON" -m venv .venv-solvers
"$AIJ_PYTHON" -m pip install -r jobs/requirements.txt -r analysis/requirements-analysis.txt
"$AIJ_PYTHON" -m pip install 'cmake==4.4.4'
cmake --version
```

CMake 是安装工具，不参与论文性能测量。随后核对 Python 中实际加载的 SCIP。如果已经是 10.1.0，不重新编译 PySCIPOpt。

```bash
"$AIJ_PYTHON" - <<'PY'
from pyscipopt import Model
m = Model()
print('Python 实际 SCIP', m.getMajorVersion(), m.getMinorVersion(), m.getTechVersion())
PY
```

**【条件执行，只有实际 SCIP 不是 10.1.0 才执行】** 为 `lib`/`lib64` 差异建立本机连接目录，然后按 [PySCIPOpt 官方构建说明](https://pyscipopt.readthedocs.io/en/latest/build.html) 从源码连接该 SCIP。

```bash
(
set -e
mkdir -p "$NLIP_SOFTWARE/scip-python"
ln -sfn "$SCIP_ROOT/include" "$NLIP_SOFTWARE/scip-python/include"
ln -sfn "$SCIP_LIBRARY_DIR" "$NLIP_SOFTWARE/scip-python/lib"
export SCIPOPTDIR="$NLIP_SOFTWARE/scip-python"
"$AIJ_PYTHON" -m pip install --force-reinstall --no-deps --no-cache-dir \
  --no-binary=pyscipopt 'pyscipopt==6.3.0'
)
```

**【直接运行】** 必须显示 `SCIP: 10.1.0` 和 `Python 依赖检查通过` 后继续。错误中缺少头文件时回到 4.2 补齐，不以降低版本绕过。

```bash
cd "$NLIP_PROJECT"
"$AIJ_PYTHON" jobs/tools/check_environment.py
```

### 4.5 编译 CaDiCaL、UWrMaxSAT 和 MaxHS

以下编译示例使用两个进程，可能需要数分钟到数十分钟。最后的链接阶段可能一段时间没有新输出。**【需要管理员确认】** 如果登录节点不允许编译，先申请交互计算资源并执行 `source "$NLIP_PROJECT/matrics.env"` 恢复模块和路径，再执行。新节点必须能访问同一软件目录。

**【直接运行，独立 CaDiCaL 3.1.0】**

```bash
(
set -e
cd "$NLIP_SOFTWARE/src/cadical-3.1.0"
./configure
make -j2
cp build/cadical "$NLIP_SOFTWARE/bin/cadical"
"$NLIP_SOFTWARE/bin/cadical" --version
)
```

**【直接运行，解析 SCIP 配套库】** 本段读取 SCIP 实际使用的 MPFR/GMP 库。

```bash
export MPFR_LIBRARY_FILE="$(ldd "$SCIP_LIBRARY_DIR/libscip.so" | awk '$1 ~ /^libmpfr\.so/ {print $3; exit}')"
export GMP_LIBRARY_FILE="$(ldd "$SCIP_LIBRARY_DIR/libscip.so" | awk '$1 ~ /^libgmp\.so/ {print $3; exit}')"
export CXX_RUNTIME_DIR="$(dirname "$(readlink -f "$(g++ -print-file-name=libstdc++.so.6)")")"
test -f "$MPFR_LIBRARY_FILE"
test -f "$GMP_LIBRARY_FILE"
mkdir -p "$NLIP_SOFTWARE/link-libs"
ln -sfn "$MPFR_LIBRARY_FILE" "$NLIP_SOFTWARE/link-libs/libmpfr.so"
ln -sfn "$GMP_LIBRARY_FILE" "$NLIP_SOFTWARE/link-libs/libgmp.so"
printf 'SCIP 库目录 %s\nMPFR %s\nGMP %s\n' "$SCIP_LIBRARY_DIR" "$MPFR_LIBRARY_FILE" "$GMP_LIBRARY_FILE"
```

若配套库无法解析，先让管理员解决 SCIP 的动态依赖。这里的软链接只建在本项目软件目录，不修改系统库。

**【直接运行，UWrMaxSAT 内部依赖与程序】** 此内部 CaDiCaL 固定为 3.0.0，与刚才独立安装的 3.1.0 分开。

```bash
(
set -e
cd "$NLIP_SOFTWARE/src/cominisatps"
for name in core simp mtl utils; do
  if [[ ! -d "$name" ]]; then ln -sfn "minisat/$name" "$name"; fi
done
cd "$NLIP_SOFTWARE/src/cadical"
patch -p1 < ../uwrmaxsat/cadical.patch
./configure --no-contracts --no-tracing
make -j2
cd "$NLIP_SOFTWARE/src/maxpre"
sed -i 's/-g/-D NDEBUG/' src/Makefile
make lib -j2
cd "$NLIP_SOFTWARE/src/uwrmaxsat"
cp config.cadical config.mk
"$AIJ_PYTHON" - <<'PY'
import os
from pathlib import Path
p = Path('config.mk')
t = p.read_text()
t = t.replace('-lmpfr', os.environ['MPFR_LIBRARY_FILE'])
t = t.replace('MCL_INCLUDE+=-I../scipoptsuite-10.0.3/scip/src -I../scipoptsuite-10.0.3/build/scip',
              'MCL_INCLUDE+=-I' + os.environ['SCIP_ROOT'] + '/include')
t = t.replace('MCL_LIB+=-L../scipoptsuite-10.0.3/build/lib -lscip -lsoplex-pic',
              'MCL_LIB+=-L' + os.environ['SCIP_LIBRARY_DIR'] + ' -lscip')
rpath = os.environ['CXX_RUNTIME_DIR'] + ':' + os.environ['SCIP_LIBRARY_DIR']
t += '\nMCL_LIB+=-Wl,-rpath,' + rpath + '\n'
p.write_text(t)
PY
make r -j2 LDFLAG_STATIC=
cp build/release/bin/uwrmaxsat "$NLIP_SOFTWARE/bin/uwrmaxsat"
)
```

如果从失败处重新编译，已经成功应用的 `patch` 不重复运行。修改源码或补丁状态不清楚时，重新解压该源码到空的新临时编译目录再做，不删正式结果。

**【直接运行，MaxHS】** 启用 SCIP 后端。

```bash
(
set -e
cd "$NLIP_SOFTWARE/src/maxhs"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DUSE_SCIP=ON \
  -DSCIP_INCLUDE="$SCIP_ROOT/include" -DSCIP_LIB="$SCIP_LIBRARY_DIR" \
  -DMPFR_LIB="$NLIP_SOFTWARE/link-libs" -DGMP_LIB="$NLIP_SOFTWARE/link-libs" \
  -DCMAKE_INSTALL_RPATH="$CXX_RUNTIME_DIR;$SCIP_LIBRARY_DIR"
cmake --build build --parallel 2
cp build/maxhs "$NLIP_SOFTWARE/bin/maxhs"
)
```

**【直接运行，安装结果检查】** 应列出六个可执行文件。`ldd` 若提示某个文件为静态程序，这是正常情况；动态程序出现 `not found` 时不能继续正式实验。

```bash
ls -l "$NLIP_MAXHS" "$NLIP_WMAXCDCL" "$NLIP_UWRMAXSAT" \
  "$NLIP_EVALMAXRES" "$NLIP_EVALMAXRES_HELPER" "$NLIP_CADICAL"
ldd "$NLIP_MAXHS"
ldd "$NLIP_UWRMAXSAT"
ldd "$NLIP_EVALMAXRES"
"$NLIP_CADICAL" --version
cd "$NLIP_PROJECT"
```

### 4.6 配置数据路径、程序路径和版本

**【必改】** 回到 `matrics.env`，确认三个数据目录是真实目录。如果源码位置改变，`NLIP_PROJECT` 也要修改。正式重跑复用冻结的 137 QPLIB、108 DiverseSAT、150 SMT 和 870 MIPO JSON；GitHub 提供清单，数据本体由项目组另外传输。

```bash
cd "$NLIP_PROJECT"
nano matrics.env
source matrics.env
test -d "$NLIP_BENCHMARK_ROOT/qplib_fully_passed"
test -d "$NLIP_BENCHMARK_ROOT/smt_0_10"
test -d "$NLIP_DIVERSE_ROOT"
test -d "$NLIP_MIPO_ROOT"
"$AIJ_PYTHON" jobs/tools/configure_cluster.py
```

预期显示 `runs: 22220`，其中 QPLIB 2192、DiverseSAT 1728、MIPO 17400、SMT 900。报缺失输入时按名称补齐，不删减清单。该命令只生成本机 `jobs/config.cluster.json`，不会下载安装软件。

**【直接运行，仅在实际安装符合第 2 部分版本时】** 以下命令写入五个外部程序的版本和模式，避免手工插入 JSON 片段导致逗号错误。

```bash
"$AIJ_PYTHON" - <<'PY'
import json
from pathlib import Path
p = Path('jobs/config.cluster.json')
c = json.loads(p.read_text())
c['solver_metadata'] = {
    'MAXHS': {'release': 'ASchidler/MaxHS b1e21b67cfe8ac2fd6b2dfb4b2b6b74eb3585740',
              'mode': 'SCIP 10.1.0; -no-lp-harden-reduced'},
    'WMAXCDCL': {'release': 'MSE2026 WMaxCDCL2026', 'mode': 'standalone'},
    'UWRMAXSAT': {'release': 'UWrMaxSat v2.0.6', 'mode': 'MaxPre; SCIP 10.1.0 sequential; -no-par'},
    'EVALMAXRES': {'release': 'MSE2026 EvalMaxRes', 'mode': 'exact; nuwls helper'},
    'CADICAL': {'release': 'CaDiCaL 3.1.0', 'mode': 'standalone sequential SAT'}
}
p.write_text(json.dumps(c, indent=2) + '\n')
print('已记录本站版本和模式')
PY
"$AIJ_PYTHON" -m json.tool jobs/config.cluster.json > /dev/null
```

`solver_paths` 是实际程序，`external_solver_args` 是运行参数，`solver_metadata` 是已核对的版本说明。填写版本文字不替代安装。配置工具预填本批的 MaxHS、UWrMaxSAT 和 EvalMaxRes 参数；只有更换实验方案时才改它们。

### 4.7 计算节点环境与许可证

**【需要管理员】** Gurobi 完整授权必须对计算节点有效。若提供许可证文件，把实际位置填写到 `matrics.env` 的 `GRB_LICENSE_FILE` 行并取消注释；若使用站点许可证服务，按管理员说明加载模块或配置服务。不能通过安装 `gurobipy` 或复制示例许可证路径获得授权。先 `source matrics.env`，再执行下面的探针。

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

重新进入项目目录，恢复环境即可。下方路径应与 4.1 一致。

```bash
cd /scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-
source matrics.env
"$AIJ_PYTHON" jobs/tools/check_environment.py
```

`matrics.env` 负责模块、解释器、软件路径及必要许可证环境，`jobs/config.cluster.json` 保存本机实际运行配置。仅恢复环境不必重新运行配置工具。若修改了 `matrics.env` 中的数据或求解器路径，要在新批次生成前重新运行 `jobs/tools/configure_cluster.py`，并核对 JSON 中的参数和版本。

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

修改可逆的本站设置时，编辑 `jobs/config.cluster.json`，保留源码和实例清单。也可以用以下方式修改某个字段，避免手工 JSON 逗号错误。**【必改】** 先将下方 `/CHANGE_ME/uwrmaxsat` 替换成实际安装路径，再执行示例。

```bash
"$AIJ_PYTHON" - <<'PY'
import json
from pathlib import Path
p = Path('jobs/config.cluster.json')
c = json.loads(p.read_text())
c['solver_paths']['UWRMAXSAT'] = '/CHANGE_ME/uwrmaxsat'
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

输出位于 `deliveries/main-new-solvers/`，验解记录包留在原批次目录。负责人审核结果后再决定是否运行该工具的 `push` 操作。
