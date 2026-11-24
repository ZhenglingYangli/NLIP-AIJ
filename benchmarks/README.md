# Benchmark lists

`manifests/` contains only the four lists used by the formal experiment.

| List | Inputs |
| --- | ---: |
| `manifests/qplib_list.txt` | 137 |
| `manifests/diverse_sat_cnf_list_no_bmc.txt` | 108 |
| `manifests/mipo_list.txt` | 870 |
| `manifests/smt_list_small.txt` | 150 |

Raw inputs are stored at the paths set in `matrics.env`. These names and the selected instances remain fixed for the experiment.

## SMT selection provenance

`smt_candidates.txt` preserves the original 2,586 candidate names. It documents the selection pool and is not a second experiment input list. The selection report recorded a minimum degree of 3 and the counts below.

```text
target=150
selected=150
min_degree=3
missing=0
parse_fail=0
source_candidate_counts:
  AProVE: 2409
  leipzig: 167
  2019-ezsmt: 8
  calypto: 2
source_selected_counts:
  AProVE: 149
  calypto: 1
  2019-ezsmt: 0
  leipzig: 0
degree_counts_selected:
  degree_18: 1
  degree_8: 1
  degree_7: 23
  degree_6: 16
  degree_5: 66
  degree_4: 43
```
