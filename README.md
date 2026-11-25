# NLIP-AIJ experiments

NLIPSat Toolkit core with Wallace-tree multiplication, current solver adapters and paper experiment statistics. The main matrix contains 1,265 inputs, 58 configurations and 22,220 runs. A separate sharing ablation has two configurations and 1,020 runs.

## Files

- `codes/`: solver core, encoders, parsers, original-problem verification and baselines.
- `jobs/`: `generate_scripts.py` generates jobs; `goSolver.py` runs tests and instances.
- `benchmarks/manifests/`: frozen input lists.
- `sumup/`: aggregation, plots and compact result export.
- `matrics.env.example`: site paths and resource settings.

Keep external solvers under `/users/scherif/ComputeSpace/solvers/`. Reuse existing binaries when their version and build mode match the experiment requirements. Install only missing versions in the `nlip-20261124/` subdirectory. Set each binary path in `matrics.env`, then regenerate `jobs/config.cluster.json`. Follow the separately supplied `NLIP_GUIDE.md` for version checks and installation steps. Then use the existing entry points:

```bash
source matrics.env
"$AIJ_PYTHON" jobs/tools/configure_cluster.py
"$AIJ_PYTHON" jobs/goSolver.py pilot
"$AIJ_PYTHON" jobs/generate_scripts.py --output results/main
bash results/main/submit.sh
```

The pilot selects four formal inputs, runs all 58 main configurations and both ablations, and prints `TEST PASSED` or `TEST FAILED` with details. Formal runs use 60 single-core workers per exclusive node, 16 GiB per instance, 970G per job and at most two simultaneous configuration jobs. Solve time is 3,600 seconds, verification 120 seconds, and the outer cap 4,000 seconds.

After the campaign:

```bash
"$AIJ_PYTHON" sumup/export_results.py --campaign results/main --summarize --push
```

Only four analysis files are committed under `experiment-results/`. Full logs, witnesses, data, binaries, licenses, environments and development tests remain outside Git. The four bundled smoke inputs and automated pilot are included.
