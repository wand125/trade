# Budget0 Replacement Path Diagnostics

日時: 2026-06-30 10:18 JST
更新日時: 2026-06-30 10:18 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00195の結論を受け、alert context限定 `budget0` が global `gap0/budget0` / `gap5/budget0` に届かない理由を `model-trade-delta` で分解した。
- all-windowでは alert context `budget0` は baseline `-90.1378` を `+6.0170` へ改善するが、global `gap0/budget0` は `+418.2596`、global `gap5/budget0` は `+508.9838`。
- late 2025-08..12では alert context `budget0` が base short `-333.9178` を除去しても、common short `-382.7524` と replacement short `-293.7604` が残り、candidate short PnL は `-676.5128` のまま。
- global `gap0/budget0` は late window の base short `-716.6702` を全て消し、replacement short を `-38.6214` に抑える。ここが alert context限定との差分。
- global `gap5/budget0` は all-window topだが、late windowでは replacement short `-286.9878` が大きく、gap0より防御が弱い。
- 結論: alert context限定ルールを増やす方向は一旦止める。次は `gap5/budget0` を early regime で使い、late deterioration では `gap0/budget0` へ落とすtriggerを、追加未使用月または追加データで再探索なし検証する。

## Artifacts

- Alert-context delta: `data/reports/backtests/20260630_011436_alert_context_budget0_vs_baseline_delta/`
- Global gap0 delta: `data/reports/backtests/20260630_011435_global_gap0_budget0_vs_baseline_delta/`
- Global gap5 delta: `data/reports/backtests/20260630_011534_global_gap5_budget0_vs_baseline_delta/`
- Comparison tables: `data/reports/backtests/20260630_011620_budget0_delta_comparison/`

Inputs:

- Baseline runs: `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10`
- Alert context `budget0`: `data/reports/backtests/20260630_005421_short_alert_context_budget_margin_recent3/match_prior_side_drift_alert/short_gap_na/threshold_inf/min_margin_inf/active_margin_minf/recover_false/entry_budget_0p0`
- Global `gap0/budget0`: `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/match_signal_short_raw_gap/short_gap_0p0/threshold_inf/min_margin_inf/recover_false/entry_budget_0p0`
- Global `gap5/budget0`: `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/match_signal_short_raw_gap/short_gap_5p0/threshold_inf/min_margin_inf/recover_false/entry_budget_0p0`

## Method

Each candidate was compared against the same `p10 + margin10` baseline with `model-trade-delta`.

```bash
python3 -m trade_data.backtest model-trade-delta \
  --base-runs data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10 \
  --candidate-runs <candidate-run-parent> \
  --output-dir data/reports/backtests \
  --label <label> \
  --top-n 20
```

The follow-up comparison groups trade deltas into:

- `all`
- `early_2025_01_07`
- `late_2025_08_12`

It also separates short exposure into `only_base`, `only_candidate`, and `common` to quantify removed shorts, replacement shorts, and remaining shared shorts.

## Results

### Window summary

| candidate | window | candidate PnL | delta vs base | candidate short PnL | removed base short | replacement short | common short |
|---|---|---:|---:|---:|---:|---:|---:|
| alert context budget0 | all | `+6.0170` | `+96.1548` | `-338.2390` | `-218.5658` | `-122.4110` | `-215.8280` |
| global gap0 budget0 | all | `+418.2596` | `+508.3974` | `+74.0036` | `-434.3938` | `+74.0036` | `0.0000` |
| global gap5 budget0 | all | `+508.9838` | `+599.1216` | `+164.7278` | `-388.5892` | `+210.5324` | `-45.8046` |
| alert context budget0 | early | `+690.9712` | `+55.9974` | `+338.2738` | `+115.3520` | `+171.3494` | `+166.9244` |
| global gap0 budget0 | early | `+465.3224` | `-169.6514` | `+112.6250` | `+282.2764` | `+112.6250` | `0.0000` |
| global gap5 budget0 | early | `+832.6886` | `+197.7148` | `+479.9912` | `+299.8054` | `+497.5202` | `-17.5290` |
| alert context budget0 | late | `-684.9542` | `+40.1574` | `-676.5128` | `-333.9178` | `-293.7604` | `-382.7524` |
| global gap0 budget0 | late | `-47.0628` | `+678.0488` | `-38.6214` | `-716.6702` | `-38.6214` | `0.0000` |
| global gap5 budget0 | late | `-323.7048` | `+401.4068` | `-315.2634` | `-688.3946` | `-286.9878` | `-28.2756` |

### Late short regime decomposition

Alert context `budget0` removes the largest late `range_low_vol` alert-context base shorts, but leaves large common and replacement losses.

| candidate | delta status | regime | rows | candidate/base short PnL |
|---|---|---|---:|---:|
| alert context budget0 | common | range_low_vol | `17` | `-213.7560` |
| alert context budget0 | common | down_normal_vol | `13` | `-57.0994` |
| alert context budget0 | common | up_normal_vol | `11` | `-38.1000` |
| alert context budget0 | only_candidate | down_low_vol | `25` | `-129.4884` |
| alert context budget0 | only_candidate | up_low_vol | `21` | `-119.8892` |
| alert context budget0 | only_candidate | range_low_vol | `1` | `-20.6556` |
| alert context budget0 | only_base | range_low_vol | `89` | `-326.5138` |

Global `gap0/budget0` is defensive because it removes all late baseline shorts and admits only small replacement short exposure.

| candidate | delta status | regime | rows | candidate/base short PnL |
|---|---|---|---:|---:|
| global gap0 budget0 | only_base | range_low_vol | `106` | `-540.2698` |
| global gap0 budget0 | only_base | down_normal_vol | `13` | `-57.0994` |
| global gap0 budget0 | only_base | up_normal_vol | `12` | `-42.7800` |
| global gap0 budget0 | only_base | range_normal_vol | `21` | `-34.3338` |
| global gap0 budget0 | only_candidate | range_normal_vol | `10` | `-35.2554` |
| global gap0 budget0 | only_candidate | range_low_vol | `3` | `-22.8980` |
| global gap0 budget0 | only_candidate | up_normal_vol | `1` | `+33.2600` |

Global `gap5/budget0` keeps early opportunity and wins all-window, but late replacement short is still large.

| candidate | delta status | regime | rows | candidate/base short PnL |
|---|---|---|---:|---:|
| global gap5 budget0 | only_base | range_low_vol | `104` | `-519.2542` |
| global gap5 budget0 | only_candidate | range_low_vol | `39` | `-192.2374` |
| global gap5 budget0 | only_candidate | up_low_vol | `5` | `-107.5956` |
| global gap5 budget0 | common | range_low_vol | `2` | `-21.0156` |

## Interpretation

- Alert-context-only `budget0` is too narrow. It removes `-333.9178` of late base short loss, but still carries `-382.7524` common short and adds `-293.7604` replacement short.
- The global `gap0/budget0` effect is not merely "alert contextを止める"ことではない。Late window の short side をほぼ全面的に退避し、replacement short damageを `-38.6214` に抑えることが本質。
- `gap5/budget0` is attractive because early window short PnL is `+479.9912` and all-window total is best. But late window replacement short `-286.9878` is large enough that, deterioration検知後は `gap0/budget0` へ落とす必要がある。
- 00191の `gap5/budget0 -> gap0/budget0` trigger はこの構造と合う。ただし min8ではNoTrade未満なので、標準採用前に追加未使用月または追加データで固定検証が必要。

## Decision

- Do not continue with more alert-context-only gates as the main line.
- Keep alert context tooling as attribution / diagnostics.
- Treat fixed global `gap0/budget0` as a defensive diagnostic baseline.
- Treat global `gap5/budget0` as an opportunity-preserving candidate that needs deterioration trigger.
- Next work:
  - fixed fresh verification of `gap0/budget0`, `gap5/budget0`, and `gap5 -> gap0` trigger without re-search,
  - replacement short diagnostics for candidate-only late trades,
  - additional data / months before promoting any budget0 policy.

## Verification

- `python3 -m trade_data.backtest model-trade-delta ... --label alert_context_budget0_vs_baseline_delta`: OK
- `python3 -m trade_data.backtest model-trade-delta ... --label global_gap0_budget0_vs_baseline_delta`: OK
- `python3 -m trade_data.backtest model-trade-delta ... --label global_gap5_budget0_vs_baseline_delta`: OK
- Comparison artifact generated: `data/reports/backtests/20260630_011620_budget0_delta_comparison/`
