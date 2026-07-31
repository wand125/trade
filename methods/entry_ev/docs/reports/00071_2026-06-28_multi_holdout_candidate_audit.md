# Multi Holdout Candidate Audit

日時: 2026-06-28 22:28 JST
更新日時: 2026-06-28 22:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

単月holdoutの見え方に引っ張られないよう、`model-policy` / `model-cost-sensitivity` の既存artifactを候補keyで復元し、複数holdoutを同時に監査する `model-holdout-audit` を追加した。

直近のside EV penalty候補群を、validation summaryと結合して 2024-12 / 2025-02 の2ヶ月で監査した。結果は、標準条件でもcost stressでも `audit_eligible=True` は0件。validation上は全候補がeligibleでも、2ヶ月同時の固定holdoutでNoTrade超えを維持できない。

## Implementation

追加:

- `read_holdout_run_frame`
- `read_holdout_run_frames`
- `summarize_holdout_audit`
- CLI: `python3 -m trade_data.backtest model-holdout-audit`

このCLIは、以下を読み込める。

- `model-policy` の `metrics.json` + `config.json`
- `model-cost-sensitivity` の `metrics.csv` + `config.json`
- run directory単体
- run directoryを複数含む親directory

`model_policy_config` から `SWEEP_KEY_COLUMNS` を復元し、validation summaryと同じ候補keyでmergeする。標準出力は要点列だけに絞り、CSVには全列を保存する。

## Validation Selection Input

まず、`short:up_low_vol` side EV penalty sweepのbase/cost-mid validationから候補母集団を作った。

Criteria:

- validation folds: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- base/cost-mid両方
- `min_folds=4`
- `min_trades_per_fold=10`
- `max_forced_exit_rate=0.05`
- `max_drawdown=150`
- `min_base_adjusted_pnl_per_fold=0`
- `min_cost_adjusted_pnl_per_fold=0`

Validation top:

| side EV penalty | min rank | base min pnl | base sum pnl | cost min pnl | cost sum pnl |
|---|---:|---:|---:|---:|---:|
| `long:ny_late:15` | `0.0` | `93.8904` | `424.0446` | `88.8904` | `404.6046` |
| `long:ny_late:15` | `0.5` | `85.7834` | `440.0672` | `80.9834` | `421.1472` |
| none | `0.5` | `81.5352` | `396.9782` | `76.4152` | `374.1782` |
| none | `0.0` | `75.0216` | `389.4214` | `69.6616` | `366.1014` |
| `long:ny_late:15,short:up_low_vol:10` | `0.0` | `69.8078` | `478.9268` | `60.8478` | `447.2868` |
| `long:ny_late:15,short:up_low_vol:10` | `0.5` | `63.6080` | `501.3944` | `55.2480` | `470.9144` |

## Standard Holdout Audit

Holdout cases:

- 2024-12 fixed tests
- 2025-02 fixed tests
- pass condition: each case adjusted pnl `>= 0`, trades `>= 10`, forced exit rate `<= 0.05`, max DD `<= 150`

| side EV penalty | min rank | validation eligible | holdout cases | pass cases | holdout min pnl | holdout sum pnl | positive rate | max DD | audit eligible |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `long:ny_late:15` | `0.5` | true | `2` | `1` | `-5.4938` | `73.9080` | `0.5000` | `113.6334` | false |
| `long:ny_late:15` | `0.0` | true | `2` | `1` | `-15.0538` | `44.1316` | `0.5000` | `123.5044` | false |
| none | `0.5` | true | `2` | `1` | `-54.6032` | `27.2302` | `0.5000` | `99.3504` | false |
| `long:ny_late:15,short:up_low_vol:10` | `0.0` | true | `2` | `1` | `-77.3720` | `-48.8242` | `0.5000` | `123.2378` | false |
| `long:ny_late:15,short:up_low_vol:10` | `0.5` | true | `2` | `1` | `-79.1486` | `-15.0562` | `0.5000` | `126.1048` | false |
| `short:up_low_vol:10` | `0.5` | true | `2` | `1` | `-134.4310` | `-67.6280` | `0.5000` | `183.2702` | false |

`long:ny_late:15` risk topは最も近いが、2024-12で `-5.4938` なのでNoTradeを超えられない。標準採用には足りない。

## Cost Stress Audit

Holdout cases:

- 2024-12 cost stress
- 2025-02 cost stress
- each candidate: `36` cases
- pass condition: each case adjusted pnl `>= 0`, trades `>= 10`, forced exit rate `<= 0.10`, max DD `<= 250`

| side EV penalty | min rank | holdout cases | pass cases | holdout min pnl | holdout sum pnl | positive rate | max DD | audit eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `long:ny_late:15` | `0.5` | `36` | `19` | `-26.0816` | `688.9690` | `0.5278` | `125.4698` | false |
| `long:ny_late:15` | `0.0` | `36` | `15` | `-28.6638` | `10.0784` | `0.4167` | `134.9444` | false |
| none | `0.5` | `36` | `18` | `-76.3910` | `-172.8610` | `0.5000` | `115.2030` | false |
| `long:ny_late:15,short:up_low_vol:10` | `0.5` | `36` | `18` | `-104.9364` | `-992.9386` | `0.5000` | `147.0926` | false |
| `short:up_low_vol:10` | `0.5` | `36` | `18` | `-161.8988` | `-1960.2060` | `0.5000` | `205.5380` | false |

Cost stressでも、`long:ny_late:15` risk topは相対的に最良だが、全case通過はできない。

## Findings

- validationだけなら20候補がeligibleになるが、固定holdoutを同時に見ると全滅する。
- `long:ny_late:15` は2024-12の損失をかなり縮めるため診断候補として有用。ただし `0` を超えないので標準policyにはできない。
- `short:up_low_vol` 直接減点は、validation上のsum pnlを増やす候補があっても、holdout監査ではbaselineより悪い。
- 今回のauditは「既知holdoutに合わせて選ぶ」ためではなく、候補の壊れ方を単月ではなく複数月・複数コストで可視化するための監査層として使う。

## Decision

- `model-holdout-audit` は採用前監査ツールとして残す。
- 現在のside EV penalty候補は、標準policyへ昇格しない。
- 次は手作業のgroup penalty探索ではなく、entry/side EV calibrationの質を上げる。特に、side/regime別の実現PnLをsupport-awareに扱うtarget、または候補選定後のEV過大評価を直接抑えるcalibrationを優先する。

## Artifacts

- validation selection: `data/reports/backtests/hgb_entry_mlp_exit_multi_holdout_audit_validation_selection/20260628_132635_model_candidate_selection/`
- standard holdout audit: `data/reports/backtests/hgb_entry_mlp_exit_multi_holdout_audit_standard/20260628_132802_model_holdout_audit/`
- cost stress audit: `data/reports/backtests/hgb_entry_mlp_exit_multi_holdout_audit_cost_stress/20260628_132803_model_holdout_audit/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_backtest`
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
