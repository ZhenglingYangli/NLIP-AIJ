# MatriCS 从零操作手册

更新于 2026-11-24。命令在 MatriCS 终端执行，每次复制一个代码块。终端提示符不要复制进去。遇到报错，先处理当前步骤，再往下执行。

日常保持原来的两个入口。`jobs/generate_scripts.py` 生成作业，`jobs/goSolver.py` 运行实例。每批生成的 `submit.sh` 自动提交作业，Slurm 自动调用运行器。首次部署使用 `jobs/tools/` 中已有的配置工具。

## 1. 地点与数字

交付顺序是广州 Ubuntu 开发 → GitHub → 合作者在 MatriCS 拉取。

| 位置 | 用途 |
| --- | --- |
| `/home/ubuntu/#科研项目/MIS/3-NLIP_AIJ` | 广州活动开发和测试目录 |
| `/home/ubuntu/NLIP-Journal-Artifact-publish` | 广州准备 GitHub 提交的目录 |
| `ZhenglingYangli/NLIP-Journal-Artifact-` | GitHub 仓库 |
| `/scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-` | MatriCS 代码与实验目录 |

| 数字 | 含义 |
| --- | --- |
| 1,265 | 正式输入总数 |
| 58 | 数据族、编码和求解器组成的配置总数 |
| 22,220 | 全部配置展开后的正式求解调用总数 |
| 60 | 一个正式配置最多同时处理的实例数，每实例一个物理核 |
| 1 | 同时运行的配置数，数组参数为 `0-57%1` |

例如 QPLIB 的 BIN + WMaxCDCL 是一个配置，有 137 个输入。最多同时处理 60 个输入，空出的工作进程领取剩余输入。整个配置结束后，Slurm 才运行下一个配置。小测覆盖相同的 58 个配置，每配置一个已知答案的输入，默认只用一个工作进程。

## 2. 首次部署需要的信息

请合作者或集群管理员提供以下实际位置。带“请填写”的示例必须替换后再执行。

- 本站 Python 3.12 的路径或模块名。
- 已安装的 SCIP 10.1.0 及其头文件、动态库所在目录。
- MaxHS、WMaxCDCL、UWrMaxSAT、EvalMaxRes、CaDiCaL 3.1.0、nuwls 的可执行文件位置、发行版本和模式。
- 原来的 QPLIB、DiverseSAT、SMT 数据位置，以及 870 个已转换 MIPO JSON 文件目录。
- 计算节点可用的完整 Gurobi 许可证。

数据、求解器二进制和许可证不随 GitHub 下载。广州当前选用的具体版本和模式见 [求解器版本说明](SOLVER_VERSIONS.md)。其中 UWrMaxSAT 已更新为 2.0.6，正式 SMT 使用独立 CaDiCaL 3.1.0，MaxHS 使用维护分支的新提交。MatriCS 按该版本表安装实际程序。

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

## 3. 取得代码

已有 checkout 时执行下面的命令。

```bash
cd /scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-
git status --short
squeue --me
git pull --ff-only
git log -1 --oneline
ls jobs/generate_scripts.py jobs/goSolver.py
```

`git status --short` 应没有待提交的源码修改。有修改时保留并与交付者核对，不使用 `reset --hard`。如果旧实验仍在使用这个目录，等它完成后再拉取。最后两个文件都存在，才继续。

第一次下载、目录尚不存在时，改用下面一组命令。

```bash
mkdir -p /scratch/scherif/NLIP/AIJ
cd /scratch/scherif/NLIP/AIJ
git clone https://github.com/ZhenglingYangli/NLIP-Journal-Artifact-.git
cd NLIP-Journal-Artifact-
```

## 4. 准备 Python 环境

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

## 5. 填写本站路径和版本

从项目根目录执行，将以下路径替换成第 2 步拿到的真实位置。数据根目录下应包含 `qplib_fully_passed` 和 `smt_0_10` 等子目录。

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

## 6. 计算节点环境和许可证

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

## 7. 提交 58 个小测试

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

## 8. 生成并提交正式主批

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

## 9. 看进度、收结果

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

## 10. 下次登录与交付状态

下次登录回到目录，重新设置解释器，并加载首次运行所需的模块和动态库环境。

```bash
cd /scratch/scherif/NLIP/AIJ/NLIP-Journal-Artifact-
export AIJ_PYTHON="$PWD/.venv-solvers/bin/python"
```

路径已经保存在 `jobs/config.cluster.json`，无需每次重填。新实验批次使用有意义的新结果目录，已有正式结果保留。

本次源码由广州验证后同步到 GitHub。拉取后以 `git log -1` 确认所用提交。MatriCS 的实际新版二进制、完整许可证、计算节点环境及配额按本手册在本站确认。Ubuntu 验证详情见 [代码和实验说明](CODE_GUIDE.md)。
