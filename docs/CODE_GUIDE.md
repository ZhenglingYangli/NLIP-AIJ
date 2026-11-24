# NLIP-AIJ 当前代码、实验与验证说明

更新于 2026-11-24。本说明对应广州活动代码和准备中的 GitHub 交付代码。运行说明见 [MatriCS 从零操作手册](COLLABORATOR_GUIDE.md)。

## 1. 这套代码做什么

它读取有界整数优化或判定问题，用 NLIP 编码转换成 SAT/MaxSAT，调用指定后端求解，并与直接建模的基线比较。每次运行都记录时间、内存、求解状态和模型规模。返回的赋值回到原问题中验解；优化目标使用原始目标重新计算。结果最终汇成表格与图，用于 NLIP-AIJ 论文实验。

主实验覆盖 QPLIB、DiverseSAT 应用模型、MIPO 和有界 SMT。LRN 在这批实验中关闭。既有 LRN 正式 2,040 条原始记录保持只读。

## 2. 代码在哪里

| 位置 | 职责 |
| --- | --- |
| 广州 `/home/ubuntu/#科研项目/MIS/3-NLIP_AIJ` | 实际开发、修复和 Ubuntu 测试 |
| 广州 `/home/ubuntu/NLIP-Journal-Artifact-publish` | 从活动目录选取正式源码，准备 GitHub 提交 |
| GitHub `ZhenglingYangli/NLIP-Journal-Artifact-` | 向合作者交付代码 |
| MatriCS `/scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-` | 合作者拉取代码后生成本站计划并运行 |
| Windows `D:/Users/yang/Documents/ChatGPT/NLIP-AIJ/AIJ写作/04-AIJ实验运行` | 当前源码和说明的本地查阅镜像 |

Ubuntu 开发、GitHub 同步、MatriCS 拉取一直是同一条链。单独的 publish 目录只用于整理提交内容。它不会自动推送，也不是另一套正式实验。

## 3. 两个入口与原始代码的关系

最早参考代码由 `generate_scripts.py` 写 Slurm 文件，由 `goSolver.py` 批量调用求解器并监督时间、内存。现在保留相同文件名和职责。

| 入口 | 现在做的事 | 对原始结构的保留 |
| --- | --- | --- |
| `jobs/generate_scripts.py` | 读取配置和方法矩阵，检查环境与输入，写计划和提交脚本 | 仍是“确定任务 → 设置 Slurm 资源 → 写作业与提交命令” |
| `jobs/goSolver.py` | 执行小测、单个配置，或 Slurm 数组指定的配置 | 仍是“取得实例 → 并行运行 → 控制资源 → 保存结果” |

生成器输出 `campaign.json` 和 `submit.sh`。Slurm 使用共享的 `jobs/internal/run_slurm.sh` 模板，从数组序号确定任务，再调用 `goSolver.py`。数组作业减少重复 Slurm 文件，作用与逐配置写脚本相同。

当前实现保留了已修好的原问题验解、精确目标计算、状态区分和续跑处理。代码不是与旧版逐行相同。旧版的批量监控职责现在由内部模块共同完成，避免把模型适配、资源监督和结果统计全放进一个文件。这里没有额外的总控入口，原来的 `run_cluster_pipeline.sh` 和 `generate_slurm.py` 已撤下。

两项目采用相同的入口分工。DiverseSAT 当前交接源码也使用 `jobs/generate_scripts.py` 和 `jobs/goSolver.py`，共享实验配置位于 `jobs/internal/experiment.py`，辅助执行程序位于 `jobs/internal/`。NLIP 的共享实验计划逻辑放在 `jobs/internal/experiment.py`，由生成器和运行器共同调用，无需单独执行。该模块除了组合定义，还负责读取本站路径、展开实例清单和分配任务编号，因此保留为内部模块，避免在两个入口中重复实现。

DiverseSAT 的独立编码阶段与 NLIP 的全过程计时各自服务于论文实验口径，统一入口职责不改变这一区别。

## 4. 目录结构

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

## 5. 当前正式实验矩阵

| 数据族 | 输入数 | 编码及后端 | 直接建模基线 | 配置数 | 运行数 |
| --- | ---: | --- | --- | ---: | ---: |
| QPLIB | 137 | OH、UNA、BIN × MaxHS、WMaxCDCL、UWrMaxSAT、EvalMaxRes | SCIP-native、Z3、CP-SAT、Gurobi | 16 | 2,192 |
| DiverseSAT 应用模型，k=2 | 108 | 同上 | 同上 | 16 | 1,728 |
| MIPO | 870 | OH、UNA、BIN、BIN+D × 上述四后端 | 同上 | 20 | 17,400 |
| 有界 SMT | 150 | OH、UNA、BIN、BIN+D × CaDiCaL | Z3、cvc5 | 6 | 900 |
| 合计 | 1,265 | | | 58 | 22,220 |

BIN+D 使用已有分解设置。SCIP、Gurobi 和 CP-SAT 直接接收有界整数多项式模型，非线性乘积通过相应乘积约束或有界中间变量表达。cvc5 用于 SMT 判定。核心仍保留 RC2 开发与回归接口，但主批不选 RC2、Open-WBO、CPLEX 或两条 MILP 扩展路线。

独立的共享消融为 MIPO/WMaxCDCL 和 SMT/CaDiCaL 共 1,020 次运行，与主批分开。

## 6. 58 和 60 的区别

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

## 7. 一次实例运行经历什么

生成器展开实例清单并记录本批方法与预算。提交后，Slurm 分配资源，`goSolver.py` 取得对应配置，内部运行器逐个启动 worker。worker 解析输入，进行预处理和编码或直接建模，再调用后端。监督器从进程启动开始计时，控制整棵进程树的资源。后端返回可行解时进入单独的验解阶段，核对原始约束和目标。

每个实例的 `result.json` 记录终态、时间、模型信息及可用的赋值证据。全部结束后汇成 `results.csv`，再生成 `analysis/` 和 `sumup/`。OPTIMAL、FEASIBLE、SAT、UNSAT、TIMEOUT、OOM、INVALID、LICENSE_LIMIT 和 UNSUPPORTED 分开保留；没有终态记录的是 PENDING。

SAT 或可行优化解必须通过原问题验解。UNSAT 没有可行赋值可验，本套实验记录后端的不可行终态，不提供每个 UNSAT 的独立证明检查。公开参考解核对和小域穷举测试用于验证相关接口与建模语义。

## 8. 本轮修改与 Ubuntu 验证

本轮把入口恢复为原始生成器与运行器的名字、分工，修改 Slurm 调用及文档，保留原先修复的执行核心。环境检查由生成器调用；自动生成的提交脚本保存编号并阻止重复提交。修复了重新配置 EvalMaxRes 时，显式指定的新 nuwls 路径没有替换旧路径的问题。小测资源缩为一个工作进程、每元素五分钟。

2026-11-24 在广州真实环境完成以下验证。

| 检查内容 | 结果 |
| --- | --- |
| 58 个配置，通过实际 Slurm 模板调用运行器，逐项执行 | 52 OPTIMAL、6 SAT，全部已知答案匹配，全部返回解验解通过 |
| 实验运行、后端、资源监督与分析测试 | 升级后 41 项通过 |
| 求解核心测试 | 50 项通过 |
| 公共 API 检查 | 56/56 通过 |
| 续跑 | 已完成实例结果未重新生成 |
| 结果汇总和绘图 | 正常完成 |
| 正式计划 | 展开为 58 配置、22,220 次调用 |
| 正式输入检查 | 137 个 QPLIB、108 个 DiverseSAT、870 个 MIPO 均实际解析通过；150 个 SMT 确认清单文件存在，语义由接口测试和运行时验解覆盖 |
| 提交脚本模拟 | 数组参数、分析依赖、编号保存、重复提交拦截通过 |
| Shell 语法 | 执行模板、提交脚本和分析脚本通过 |

58 次集成小测来自四个已知答案的小模型在各配置下运行，不是 58 个不同的大型实例。41 项运行测试包含真实外部求解器、与独立穷举的比较，以及超时、进程树清理、内存超限、验解预算、状态冲突和缺失结果处理。测试计数按各套件报告，不将重复覆盖算作新增实例。

升级后的验证日志保存在广州 `results/solver-refresh-20261124/`，本次交付副本验证保存在 `results/github-delivery-20261124/`。Slurm 提交命令使用临时模拟程序验证，没有向真实集群提交。小测性能不用于论文加速结论。

## 9. 交付范围与尚待完成的事项

GitHub 交付包括源码、配置起点、实例清单、小测输入、依赖说明、测试和操作文档。机器配置、Python 环境、求解器二进制、许可证、原始数据、正式运行结果和历史研究草稿不混入源码提交。

当前交付说明和最终验证结果见 [完整操作手册](EXPERIMENT_HANDBOOK.md)。MatriCS 正式实验尚未开始。MatriCS 需要按版本说明部署对应的外部求解器，完成计算节点检查，确认完整 Gurobi 许可证与配额。广州再次运行 2001 变量许可证探针，返回 10010 规模受限错误，因此当前广州许可证不能用于完整规模实验。

同日后续已完成 UWrMaxSAT 2.0.6、维护分支新版 MaxHS 和独立 CaDiCaL 3.1.0 的安装与切换。当前版本和参数以 [求解器版本说明](SOLVER_VERSIONS.md) 为准，该说明同时记录升级后验证。MatriCS 仍须安装并验证这一组实际程序。
