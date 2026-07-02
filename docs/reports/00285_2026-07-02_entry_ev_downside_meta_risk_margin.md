# Entry EV Downside Meta Risk Margin

日時: 2026-07-02 11:57 JST
更新日時: 2026-07-02 11:57 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00284でrejectした hard block の代わりに、raw cd15 scoreへ soft downside risk margin を入れた。
- `scripts/experiments/entry_ev_downside_meta_risk_margin_policy_inputs.py` を追加し、`raw_score - weight * pred_downside_meta_expected_downside` のlong/short score列とquantile列を生成した。
- weightは gentle `0.1/0.25/0.5` と stress `1/2/5/10` を試した。
- 結果は不採用。best totalは `w0p25` の `+23.7938` で、baseline `+118.6900` を大きく下回る。`w1` はmonth minを `-5.6864` まで少し改善するが、total `+18.9676`, role min `-3.9590`, positive roles `3/6` で標準候補にならない。
- 判断: downside meta scoreを直接entry scoreへ足し引きする経路もreject。downside metaはraw score変換ではなく、stateful replay結果を目的に含むcandidate-level selector / diagnostic featureとして使う。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_downside_meta_risk_margin_policy_inputs.py`
- Test:
  - `tests/test_entry_ev_downside_meta_risk_margin_policy_inputs.py`
- Gentle input runs:
  - `data/reports/backtests/20260702_025250_20260702_entry_ev_downside_meta_risk_margin_gentle_cal2024_s1/`
  - `data/reports/backtests/20260702_025300_20260702_entry_ev_downside_meta_risk_margin_gentle_fresh2024_s1/`
  - `data/reports/backtests/20260702_025323_20260702_entry_ev_downside_meta_risk_margin_gentle_refit2025_s1/`
  - `data/reports/backtests/20260702_025347_20260702_entry_ev_downside_meta_risk_margin_gentle_hgb2024_0306_s1/`
  - `data/reports/backtests/20260702_025359_20260702_entry_ev_downside_meta_risk_margin_gentle_hgb2025_08_s1/`
  - `data/reports/backtests/20260702_025410_20260702_entry_ev_downside_meta_risk_margin_gentle_hybrid2025_0912_s1/`
- Stress input runs:
  - `data/reports/backtests/20260702_024806_20260702_entry_ev_downside_meta_risk_margin_cal2024_s1/`
  - `data/reports/backtests/20260702_024819_20260702_entry_ev_downside_meta_risk_margin_fresh2024_s1/`
  - `data/reports/backtests/20260702_024842_20260702_entry_ev_downside_meta_risk_margin_refit2025_s1/`
  - `data/reports/backtests/20260702_024910_20260702_entry_ev_downside_meta_risk_margin_hgb2024_0306_s1/`
  - `data/reports/backtests/20260702_024922_20260702_entry_ev_downside_meta_risk_margin_hgb2025_08_s1/`
  - `data/reports/backtests/20260702_024933_20260702_entry_ev_downside_meta_risk_margin_hybrid2025_0912_s1/`
- Replay runs:
  - `data/reports/backtests/20260702_025434_20260702_entry_ev_downside_meta_risk_margin_w0p1_replay_s1/`
  - `data/reports/backtests/20260702_025515_20260702_entry_ev_downside_meta_risk_margin_w0p25_replay_s1/`
  - `data/reports/backtests/20260702_025553_20260702_entry_ev_downside_meta_risk_margin_w0p5_replay_s1/`
  - `data/reports/backtests/20260702_025004_20260702_entry_ev_downside_meta_risk_margin_w1_replay_s1/`
  - `data/reports/backtests/20260702_025047_20260702_entry_ev_downside_meta_risk_margin_w2_replay_s1/`
  - `data/reports/backtests/20260702_025124_20260702_entry_ev_downside_meta_risk_margin_w5_replay_s1/`
  - `data/reports/backtests/20260702_025159_20260702_entry_ev_downside_meta_risk_margin_w10_replay_s1/`

## Method

Score transform:

```text
long_margin_score  = raw_long_score  - weight * max(long_expected_downside, 0)
short_margin_score = raw_short_score - weight * max(short_expected_downside, 0)
```

Replay settings:

```text
candidate = q95_sg95_rank90_floor5_side_regime_session_month
variant = loss_exit30_cd15
profit_multiplier = 1.0
loss_multiplier = 1.2
max_hold = 24h
entry quantiles = recomputed on margin score_kind for each weight
```

This keeps the raw cd15 benchmark structure but allows risk margin to change selected side, selected score quantile, and side-gap quantile.

## Score Effect

Average row-level effect:

| weight | side switch share | selected score delta mean | margin q95 |
|---:|---:|---:|---:|
| `0.10` | `0.0199` | `-0.0396` | `6.9745` |
| `0.25` | `0.0271` | `-0.0986` | `6.8972` |
| `0.50` | `0.0394` | `-0.1955` | `6.7784` |
| `1.00` | `0.0621` | `-0.3847` | `6.5769` |
| `2.00` | `0.0996` | `-0.7478` | `6.2515` |
| `5.00` | `0.1754` | `-1.7591` | `5.5643` |
| `10.00` | `0.2427` | `-3.3243` | `4.9902` |

Reading:

- Even weak margin changes the rank/quantile boundary enough to remove many baseline trades.
- Strong margin creates side-switch behavior similar to the rejected shrinkage score replacement path.

## Stateful Replay

Combined internal/HGB + hybrid:

| run | total pnl | trades | month min | role min | positive roles | max DD | decision |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline raw cd15 | `+118.6900` | `266` | `-6.8324` | `+0.0074` | `6/6` | `30.8714` | NoTrade |
| w0.1 | `+22.4812` | `186` | `-8.7992` | `-6.6384` | `4/6` | `22.6582` | reject |
| w0.25 | `+23.7938` | `177` | `-7.7558` | `-5.9184` | `4/6` | `21.1908` | reject |
| w0.5 | `+21.7298` | `178` | `-8.4858` | `-0.2120` | `3/6` | `21.3142` | reject |
| w1 | `+18.9676` | `160` | `-5.6864` | `-3.9590` | `3/6` | `17.2200` | reject |
| w2 | `-0.3652` | `146` | `-16.7840` | `-12.5214` | `2/6` | `18.1440` | reject |
| w5 | `-0.1982` | `106` | `-14.2092` | `-9.2924` | `2/6` | `16.2262` | reject |
| w10 | `+1.9740` | `107` | `-13.5568` | `-5.7944` | `2/6` | `14.6068` | reject |

Worst months for representative weights:

| run | family | month | pnl | trades |
|---|---|---|---:|---:|
| w0.25 | hgb2024_0306 | 2024-06 | `-7.7558` | `16` |
| w0.25 | refit2025 | 2025-02 | `-6.2576` | `10` |
| w0.25 | hybrid2025_0912 | 2025-12 | `-6.2184` | `3` |
| w0.5 | hgb2024_0306 | 2024-06 | `-8.4858` | `19` |
| w0.5 | refit2025 | 2025-02 | `-6.2576` | `10` |
| w1 | refit2025 | 2025-04 | `-5.6864` | `22` |
| w1 | hgb2024_0306 | 2024-06 | `-5.5764` | `21` |
| w1 | hybrid2025_0912 | 2025-12 | `-4.7160` | `1` |

Reading:

- Weak weights do not protect tail and still destroy total PnL.
- Weight `1` modestly improves month min, but only by deleting too much profitable exposure; role min becomes negative.
- Strong weights reduce trade count and max DD, but this is not useful because they lose the baseline edge and fail role/month gates.

## Decision

Accepted:

- downside meta soft-margin score input generation
- multi-weight quantile regeneration
- replay evidence that score-level downside adjustment is not enough

Rejected:

- `raw_score - weight * expected_downside` as a policy score
- tuning weight to rescue the raw cd15 candidate
- treating lower max DD alone as success when total and role floors collapse

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark.

## Next

1. Stop direct score transforms using downside meta for now.
2. Move to candidate-level stateful meta selection: evaluate candidate variants by predicted risk features but optimize month floor, role floor, trade support, and total PnL together.
3. Keep downside meta, supervised shrinkage, loss-first probability, predicted holding, side gap, and capture diagnostics as selector features rather than score arithmetic.
4. Consider preserving raw entry side/score and only adjusting admission thresholds by role/month support, to avoid side-switch path instability.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_downside_meta_risk_margin_policy_inputs.py tests/test_entry_ev_downside_meta_risk_margin_policy_inputs.py`: OK
- `uv run python -m unittest tests.test_entry_ev_downside_meta_risk_margin_policy_inputs`: OK
- downside risk margin input generation for 6 families and 7 weights: OK
- risk margin replay for 7 weights: OK
