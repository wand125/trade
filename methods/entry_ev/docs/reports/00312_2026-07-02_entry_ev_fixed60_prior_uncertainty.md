# Entry EV Fixed60 Prior Uncertainty

日時: 2026-07-02 17:51 JST
更新日時: 2026-07-02 17:51 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00311の次アクションとして、`long_range_normal_ny_fixed60_pred_gt0` をhard blockへ進めず、短期path過大評価をprior-only uncertainty feature候補へ戻した。
- `scripts/experiments/entry_ev_short_horizon_prior_uncertainty.py` を追加し、`selected_fixed_60m_pred_pnl > 0` かつ `selected_fixed_60m_actual_pnl < 0` を診断targetとして、同じcontextの過去月だけからprior統計を作れるようにした。
- 対象は00310の `isolated_large_loss_long_t-5_h720` / `entryblock_none` 行。246 trades / total `+326.1098` / fixed60 false-positive 51件。
- 最良の細粒度prior ruleは `family,direction,combined_regime,session_regime` の `prior_count_ge5_pnl_neg_fp_rate_ge0p4`。4 tradesをflagし、flagged PnL `-11.4360`、3/4がfixed60 false-positive、final loss precision `1.0000`。
- このruleは00310のrefit集中4件block `+11.4912` をほぼ再現するが、flagは全て `refit2025_validation`。非refit holdoutでは同じ細粒度ruleは発火0件。
- broader holdout ruleには小幅改善があるが、false-positive precisionが低く、勝ち/通常lossを巻き込む。
- 判断: fixed60 prior uncertainty diagnosticsはaccepted infrastructure。`prior_fixed_*` 列はmodel-level uncertainty / calibration residual feature候補として残す。hard gate標準化はしない。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_short_horizon_prior_uncertainty.py`
- New test:
  - `tests/test_entry_ev_short_horizon_prior_uncertainty.py`
- Main run:
  - `data/reports/backtests/20260702_085053_20260702_entry_ev_00312_fixed60_prior_uncertainty_s1/`

## Method

Input:

```text
data/reports/backtests/20260702_082037_20260702_entry_ev_00310_position_quality_proxy_overlay_s1/entry_block_overlay_trades.csv
```

Filter:

```text
entry_block_rule = none
selector_variant contains isolated_large_loss_long_t-5_h720
discovery role = refit2025_validation
holdout = all non-refit roles
```

Diagnostic target:

```text
fixed_false_positive =
  selected_fixed_60m_pred_pnl > 0
  and selected_fixed_60m_actual_pnl < 0
```

`selected_fixed_60m_actual_pnl` はtarget / 診断結果としてのみ使う。prior featureは対象月より前の月だけから作り、同月のtrade結果はpriorに含めない。

Prior context specs:

```text
direction,session_regime
direction,combined_regime
combined_regime,session_regime
direction,combined_regime,session_regime
family,direction,combined_regime,session_regime
role,direction,combined_regime,session_regime
```

Generated prior feature examples:

```text
prior_trade_count
prior_adjusted_pnl_sum
prior_fixed_false_positive_rate
prior_fixed_actual_negative_rate
prior_fixed_overestimate_mean
prior_fixed_uncertainty_pressure
```

## Results

Base rows:

| rows | total PnL | fixed60 false-positive | final loss |
|---:|---:|---:|---:|
| `246` | `+326.1098` | `51` | `105` |

Role split:

| role | trades | PnL | fixed60 false-positive |
|---|---:|---:|---:|
| `refit2025_validation` | `113` | `+270.8392` | `34` |
| `hgb2024_0306_external` | `82` | `+24.1320` | `10` |
| `cal2024_validation` | `31` | `+6.9988` | `3` |
| `hgb2025_08_external` | `11` | `+0.5354` | `1` |
| `hybrid2025_0912_external` | `6` | `+15.2700` | `2` |
| `fresh2024_validation` | `3` | `+8.3344` | `1` |

### Best Fine Prior Rule

`family,direction,combined_regime,session_regime` / `prior_count_ge5_pnl_neg_fp_rate_ge0p4`:

| scope | flagged | flagged PnL | delta if removed | fixed60 FP flagged | FP precision | final loss precision |
|---|---:|---:|---:|---:|---:|---:|
| all | `4` | `-11.4360` | `+11.4360` | `3` | `0.7500` | `1.0000` |
| discovery refit2025 | `4` | `-11.4360` | `+11.4360` | `3` | `0.7500` | `1.0000` |
| holdout non-refit | `0` | `0.0000` | `0.0000` | `0` | `0.0000` | `0.0000` |

Flagged rows:

| role | month | direction/context | PnL | fixed60 pred | fixed60 actual | fixed60 FP | prior count | prior PnL | prior FP rate |
|---|---|---|---:|---:|---:|---|---:|---:|---:|
| `refit2025_validation` | `2025-12` | `long/range_normal_vol/ny_overlap` | `-7.5480` | `+0.5132` | `-9.6960` | true | `7` | `-7.6942` | `1.0000` |
| `refit2025_validation` | `2025-10` | `long/range_normal_vol/ny_overlap` | `-2.9880` | `+0.9762` | `-8.3520` | true | `6` | `-4.7062` | `1.0000` |
| `refit2025_validation` | `2025-09` | `long/range_normal_vol/ny_overlap` | `-0.8280` | `-0.3754` | `+3.2400` | false | `5` | `-3.8782` | `1.0000` |
| `refit2025_validation` | `2025-12` | `long/range_normal_vol/ny_overlap` | `-0.0720` | `+1.2409` | `-10.1880` | true | `7` | `-7.6942` | `1.0000` |

Reading:

- 00310の4件block `-11.4912` に近いが、2025-08 `-0.8832` はprior support不足で拾わず、2025-09 `-0.8280` のnon-FP lossを拾う。
- それでも4件すべてfinal lossで、no-replacement診断上は有用。
- ただし全てdiscovery側で、holdout supportはない。

### Context Target Distribution

`long|range_normal_vol|ny_overlap`:

| context spec | context | trades | total PnL | fixed60 FP | fixed60 FP PnL | final losses |
|---|---|---:|---:|---:|---:|---:|
| `direction,combined_regime,session_regime` | `long|range_normal_vol|ny_overlap` | `11` | `-16.0512` | `4` | `-11.4912` | `8` |
| `family,direction,combined_regime,session_regime` | `refit2025|long|range_normal_vol|ny_overlap` | `9` | `-15.3142` | `4` | `-11.4912` | `7` |
| `family,direction,combined_regime,session_regime` | `cal2024|long|range_normal_vol|ny_overlap` | `1` | `-2.6640` | `0` | `0.0000` | `1` |
| `family,direction,combined_regime,session_regime` | `hgb2024_0306|long|range_normal_vol|ny_overlap` | `1` | `+1.9270` | `0` | `0.0000` | `0` |

Reading:

- 00310/00311で問題だったcontextは、fixed60 false-positive targetでも同じく悪い。
- ただし非refit側は1 loss / 1 winnerで、fixed60 false-positiveは0件。
- この状態でcontext全体をblockすると、00311と同じくholdoutでは勝ちも巻き込む。

### Holdout Broad Rules

HoldoutでPnLだけを見ると、広いcontextには改善ruleがある。

| scope | group spec | rule | flagged | flagged PnL | FP precision | final loss precision |
|---|---|---|---:|---:|---:|---:|
| holdout | `direction,session_regime` | `prior_count_ge5_pnl_neg_fp_rate_ge0p4` | `16` | `-7.1694` | `0.0625` | `0.6250` |
| holdout | `combined_regime,session_regime` | `prior_count_ge5_fp_rate_ge0p4` | `10` | `-4.5100` | `0.2000` | `0.6000` |
| holdout | `combined_regime,session_regime` | `prior_count_ge3_fp_rate_ge0p5` | `14` | `-3.5360` | `0.1429` | `0.5714` |

Reading:

- PnL改善だけなら見えるが、false-positive precisionが低い。
- これはfixed60 targetをきれいに拾っているのではなく、広いcontextのloss/winnerをまとめて削る動き。
- 標準policyへは進めない。

## Decision

Accepted:

- fixed60 prior uncertainty diagnostics
- `prior_fixed_*` feature export
- current monthを除外したcontext prior construction
- discovery / holdout split summary

Rejected:

- `prior_count_ge5_pnl_neg_fp_rate_ge0p4` をhard gateとして採用すること
- broad prior warning ruleをPnL改善だけで採用すること
- fixed60 actual PnLを実行featureとして使うこと
- refit2025集中の再現を汎化edgeとして扱うこと

Standard policy remains NoTrade.

## Next

1. `prior_fixed_false_positive_rate`, `prior_fixed_overestimate_mean`, `prior_fixed_uncertainty_pressure`, `prior_adjusted_pnl_sum` をcandidate-level selector / uncertainty headのfeature候補に入れる。
2. hard blockではなく、expected PnL calibrationの残差・不確実性・exit timing confidenceを下げる補助特徴として使う。
3. 非refit holdoutまたは別branchで、同じprior featureがprediction qualityを上げるかを確認する。
4. feature採用後は必ずstateful replay、role/month floor、side share、NoTrade-first admissionへ戻す。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_short_horizon_prior_uncertainty.py tests/test_entry_ev_short_horizon_prior_uncertainty.py`: OK
- `uv run python -m unittest tests.test_entry_ev_short_horizon_prior_uncertainty`: OK
- `uv run python -m unittest tests.test_entry_ev_short_horizon_prior_uncertainty tests.test_entry_ev_entry_block_holdout_support_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00312 fixed60 prior uncertainty diagnostics run: OK
