# Side Regime EV Penalty

日時: 2026-06-28 21:43 JST
更新日時: 2026-06-28 21:43 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の `日時` を参照する。

## Summary

`long:session_regime=ny_late` をhard blockやside marginではなく、side別EVへの直接減点として扱う `--side-ev-penalty-rules` を追加した。

直近のHGB entry/side + MLP exit timing hybridに対して、validation 4foldで `none`, `long:ny_late:2/5/10/15` を比較した。PnL順位では `long:ny_late:15`, `min_entry_rank=0.0` がtopになり、near-top risk順位では同じ減点15の `min_entry_rank=0.5` がtopになった。

2024-12反証月では、ruleなしbaseline `-54.6032` に対し、EV減点15 + rank0.5 は `-5.4938` まで損失を縮めた。ただしNoTrade `0` には届かないため、標準policyへはまだ昇格しない。regime EV penaltyは探索軸として採用し、次は別holdout月とコストストレスで壊れ方を確認する。

## Implementation

追加した設定:

- `ModelPolicyConfig.side_ev_penalty_rules`
- `model-policy --side-ev-penalty-rules`
- `model-sweep --side-ev-penalty-rules`
- `model-sweep --side-ev-penalty-rule-sets`
- `SWEEP_KEY_COLUMNS` / `normalize_sweep_metrics` への保存・後方互換

Rule syntax:

```text
side:column=value+...:penalty
```

例:

```text
long:session_regime=ny_late:15
```

このruleは、side選択前にmatching rowsのlong EVから `15` を引く。hard blockではないので、減点後もlong EVがshort EVやentry thresholdを十分上回ればlong entryは残る。

## Setup

Input:

- OOF predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- 2024-12 predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- policy: `timed_ev`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- evaluation multipliers: profit `1.0`, loss `1.20`

Local grid:

- entry threshold: `10,15`
- short offset: `4,8`
- side margin: `3,5`
- max predicted hold: `240,480`
- min entry rank: `0,0.5`
- side EV penalty rule sets: `none`, `long:session_regime=ny_late:2`, `:5`, `:10`, `:15`

## Validation Result

PnL ranking:

| rank | side EV penalty | entry | short offset | side margin | min rank | max hold | min pnl | sum pnl | min trades | max DD | group loss | EV over max |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `long:ny_late:15` | `15` | `4` | `5` | `0.0` | `480` | `93.8904` | `424.0446` | `17` | `58.9488` | `193.3728` | `17.0634` |
| 2 | `long:ny_late:10` | `15` | `4` | `5` | `0.5` | `480` | `87.9334` | `410.3378` | `16` | `60.0744` | `232.8050` | `18.0087` |
| 3 | `long:ny_late:5` | `15` | `4` | `5` | `0.5` | `480` | `87.9334` | `410.3378` | `16` | `60.0744` | `232.8050` | `18.0087` |
| 4 | `long:ny_late:15` | `15` | `4` | `5` | `0.5` | `480` | `85.7834` | `440.0672` | `16` | `51.8988` | `179.5578` | `17.3100` |
| 9 | none | `15` | `4` | `5` | `0.5` | `480` | `81.5352` | `396.9782` | `23` | `60.0744` | `227.6878` | `16.9756` |

Best eligible by rule:

| rule | min pnl | sum pnl | min trades | max DD | group loss | max side share |
|---|---:|---:|---:|---:|---:|---:|
| `long:ny_late:15` | `93.8904` | `424.0446` | `17` | `58.9488` | `193.3728` | `0.7857` |
| `long:ny_late:10` | `87.9334` | `410.3378` | `16` | `60.0744` | `232.8050` | `0.7857` |
| `long:ny_late:5` | `87.9334` | `410.3378` | `16` | `60.0744` | `232.8050` | `0.7857` |
| `long:ny_late:2` | `85.1966` | `367.5676` | `17` | `61.9968` | `252.3560` | `0.7857` |
| none | `81.5352` | `396.9782` | `23` | `60.0744` | `227.6878` | `0.7097` |

Near-top risk ranking with tolerance `10`:

| rank | side EV penalty | min rank | min pnl | sum pnl | max DD | group loss | risk score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `long:ny_late:15` | `0.5` | `85.7834` | `440.0672` | `51.8988` | `179.5578` | `400.8094` |
| 2 | `long:ny_late:15` | `0.0` | `93.8904` | `424.0446` | `58.9488` | `193.3728` | `421.5870` |
| 3 | `long:ny_late:10` | `0.5` | `87.9334` | `410.3378` | `60.0744` | `232.8050` | `463.6295` |
| 4 | `long:ny_late:5` | `0.5` | `87.9334` | `410.3378` | `60.0744` | `232.8050` | `463.6295` |

## 2024-12 Fixed Test

| candidate | min rank | validation min pnl | validation sum pnl | 2024-12 adjusted pnl | trades | profit factor | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| ruleなし baseline | `0.5` | `81.5352` | `396.9782` | `-54.6032` | `49` | `0.7504` | `97.3520` |
| `long:ny_late:15` PnL top | `0.0` | `93.8904` | `424.0446` | `-15.0538` | `31` | `0.9154` | `69.6900` |
| `long:ny_late:15` risk top | `0.5` | `85.7834` | `440.0672` | `-5.4938` | `46` | `0.9658` | `61.1556` |

## Decision

- `side_ev_penalty_rules` は継続採用する。hard blockよりも滑らかにside/regime riskを扱える。
- 今回の `long:ny_late:15` はvalidationでも2024-12でもruleなしを改善した。ただしNoTrade `0` に届かず、max side shareも `0.7857` と高い。
- 標準policyへの昇格は保留する。次は別holdout月、コスト/遅延ストレス、penalty幅の周辺台地を確認する。
- report ordering / latest checksは、ファイル更新時刻ではなく本文の `日時` を参照する。

## Artifacts

- validation sweeps: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_sweep/`
- PnL selection: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_selection/20260628_124130_model_candidate_selection/`
- near-top risk selection: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_selection_risk/20260628_124241_model_candidate_selection/`
- 2024-12 fixed tests: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_2024_12/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_backtest`
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
