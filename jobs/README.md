# NLIP-AIJ 实验设置与执行

固定沿用最早参考代码的两个入口。`jobs/generate_scripts.py` 检查依赖，根据实验矩阵生成 Slurm 作业计划和 `submit.sh`。`jobs/goSolver.py` 负责运行实例，调用已有的时间、内存控制与原问题验解。提交后 Slurm 自动调用运行器。

`jobs/internal/` 保存共享执行实现，`jobs/internal/experiment.py` 是唯一矩阵定义。生成的 `submit.sh` 是每批实验的输出，不是需要维护的第三个入口。它提交数组及后续分析，保存作业编号，并拒绝直接重复提交。

## 正式主批

| 数据族 | 输入 | 编码后端组合 | 基线 | 配置数 | 运行数 |
| --- | ---: | --- | --- | ---: | ---: |
| QPLIB | 137 | OH、UNA、BIN × MaxHS、WMaxCDCL、UWrMaxSAT、EvalMaxRes | SCIP-native、Z3、CP-SAT、Gurobi | 16 | 2,192 |
| DiverseSAT 应用模型 | 108，固定 k=2 | 同上 | 同上 | 16 | 1,728 |
| MIPO | 870 | OH、UNA、BIN、BIN+D × 上述四后端 | 同上 | 20 | 17,400 |
| 有界 SMT | 150 | OH、UNA、BIN、BIN+D × CaDiCaL | Z3、cvc5 判定 | 6 | 900 |
| 合计 | 1,265 | | | 58 | 22,220 |

主批不含 RC2、Open-WBO、CPLEX、SCIP-MILP 或 HiGHS-MILP。RC2 仍用于既有开发回归。cvc5 只做 SMT 判定。LRN 关闭。独立共享消融的 MIPO 后端改为 WMaxCDCL，与主批共享版本配对，另有 SMT/CaDiCaL 对照，共 1,020 次，不计入主批。

BIN+D 保留阈值 3、顺序分解、精确乘法和共享。SCIP、Gurobi 接收整数多项式模型，乘积通过有界中间变量表达。CP-SAT 使用整数乘积约束。它们不是本次排除的 Boolean-product MILP 路线。超出后端可精确表达范围的输入记为 UNSUPPORTED，保留原因。

## 预算与结果

每实例一个物理核，16 GiB，3,600 秒涵盖程序启动、解析、编码和求解。原问题验解另给 120 秒，外围上限 4,000 秒。bigmem-amd 每个配置申请一个独占节点、60 个物理核、970 GiB；数组并发为 1。最大配置按 870 个实例估算，申请 19 小时。

编码和求解留在同一次受限运行中，保持全过程计时。这里不采用 DiverseSAT 的独立 transform 作业。LEX、DIAG、SEv1、SEv3 也不是本项目的参数。

OPTIMAL 必须来自后端的最优终态，且返回赋值通过原问题约束和精确目标复算。仅可行的结果记为 FEASIBLE。UNSAT、TIMEOUT、OOM、ERROR、INVALID、LICENSE_LIMIT、UNSUPPORTED 和缺失项分别保留，缺失项不当作 OOM。外部 MaxSAT 的状态行与有明确含义的退出码矛盾时记 INVALID。

原始记录位于 `results/<批次>/runs/`，计划为 `campaign.json`，总表为 `results.csv`，旧格式表为 `sumup/`，论文分析为 `analysis/`。续跑保留已有终态记录，只处理没有完成记录的任务。不同代码、环境、参数和输入不混入同一批次。

## 使用

从项目根目录执行，先按本站环境设置 `AIJ_PYTHON`，并配置四个外部 MaxSAT 求解器和独立 CaDiCaL 的实际路径。

```bash
export AIJ_PYTHON="$PWD/.venv-solvers/bin/python"
export NLIP_MAXHS=/实际路径/maxhs
export NLIP_WMAXCDCL=/实际路径/wmaxcdcl_static
export NLIP_UWRMAXSAT=/实际路径/uwrmaxsat
export NLIP_EVALMAXRES=/实际路径/EvalMaxSAT
export NLIP_EVALMAXRES_HELPER=/实际路径/nuwls
export NLIP_CADICAL=/实际路径/cadical

"$AIJ_PYTHON" jobs/tools/configure_cluster.py
"$AIJ_PYTHON" jobs/tools/check_environment.py
"$AIJ_PYTHON" jobs/generate_scripts.py --profile smoke --output results/smoke-new-solvers
bash results/smoke-new-solvers/submit.sh
```

`jobs/tools/configure_cluster.py` 是首次部署使用的辅助工具，保留本站已有数据根目录和 MIPO 路径，写入本机的 `jobs/config.cluster.json`。在该文件的 `solver_metadata` 中为四个外部后端填写实际 `release` 和 `mode`，不能只写“最新版”。`external_solver_args` 保存有效参数。广州配置不会复制到 MatriCS。

当前广州固定 Python 3.12、PySAT 1.9.dev24、Z3 5.4.1.0、PySCIPOpt 6.3.0 / SCIP 10.1.0、OR-Tools 9.15.6755、Gurobi 14.0.0、cvc5 1.4.2。依赖见 `requirements.txt`。Gurobi 14 需要 Python 3.11 或更新版本，不能复用旧的 MatriCS Python 3.9 环境。

当前选用 UWrMaxSAT 2.0.6、维护分支新版 MaxHS、MSE2026 独立 WMaxCDCL 与 EvalMaxRes，以及独立 CaDiCaL 3.1.0。具体路径、内部依赖、启动参数、模式和官方来源统一见 [求解器版本说明](../docs/SOLVER_VERSIONS.md)。正式运行必须配置五个外部程序，不能用修改版本标签代替更新程序。

小测同样通过生成器提交为 Slurm 数组，编号保存在 `results/smoke-new-solvers/array_job_id.txt`。检查全部 58 个配置的日志和汇总，确认 52 个优化结果为 OPTIMAL、6 个判定结果为 SAT，并通过已知答案和原问题验解。这组小例不能证明 Gurobi 完整许可证可用；正式 Gurobi 配置启动前还有超过受限规模的许可证探针。许可证错误不能记作算法超时。

小测通过后生成并提交主批。

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py --output results/main-new-solvers
# 核对输出为 58 configurations、22,220 runs，再执行提交
bash results/main-new-solvers/submit.sh
sacct -j "$(cat results/main-new-solvers/array_job_id.txt)" --format=JobID,State,ExitCode,Elapsed
```

提交编号保存为批次目录中的 `array_job_id.txt` 和 `analysis_job_id.txt`。生成的提交脚本拒绝直接重复提交已有作业编号的批次。需要续跑时先看 sacct 与已有记录，再决定重排哪些数组元素。分析作业依赖数组结束自动启动，也可以手动重算。

```bash
"$AIJ_PYTHON" analysis/analyze_campaign.py results/main-new-solvers
```

生成器也可单独使用，其作用仅为准备计划，不提交作业。

```bash
"$AIJ_PYTHON" jobs/generate_scripts.py --output results/main-new-solvers
```

正式提交要求求解核心和运行器代码已提交到 Git。广州活动目录的修改完成后，经 GitHub 交付，MatriCS 拉取该提交再生成本站批次。广州本次生成的路径和计划不用于 MatriCS。

在广州或已分配的计算节点上，运行器也可直接执行一个小测，不经过 Slurm。不要在集群登录节点执行求解。

```bash
"$AIJ_PYTHON" jobs/goSolver.py test qplib bin-wmaxcdcl --output results/local-smoke
```

求解器版本、路径和参数放在本站配置中，实验组合放在 `jobs/internal/experiment.py`，不为每次实验增加新的入口脚本。
