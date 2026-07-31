# Entry EV Prior Pressure Large Loss Head

日時: 2026-07-02 15:15 JST
更新日時: 2026-07-02 15:15 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00301の結論どおり、prior residual pressureをhard gateではなくlarge-loss / uncertainty headのfeatureとして使えるか診断した。
- `scripts/experiments/entry_ev_selected_trade_large_loss_head.py` を追加し、selected-trade prior pressure rowsからchronological OOF large-loss classifierを作れるようにした。
- 比較は `base` features と `base_prior` features。`base_prior` はbase特徴に prior PnL、loss rate、large-loss rate、bias、MAE、overestimate、residual pressureを加える。
- 結果は否定的。base特徴だけのほうが良く、prior pressureを足すとAUC / AP / Brierが悪化した。
- high-risk除去も全て悪化。最も悪化幅が小さい `factor base_prior prob_ge_0.4` でも2 trades / flagged PnL `+15.0000` で、勝ちtradeだけを削った。
- 判断: large-loss head infrastructureはaccepted。現prior pressure feature追加はreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_selected_trade_large_loss_head.py`
- New test:
  - `tests/test_entry_ev_selected_trade_large_loss_head.py`
- Main run:
  - `data/reports/backtests/20260702_061536_20260702_entry_ev_prior_pressure_large_loss_head_s1/`

## Input

```text
data/reports/backtests/20260702_060145_20260702_entry_ev_residual_combo_prior_residual_pressure_s1/selected_trade_prior_residual_pressure_rows.csv
```

Run setting:

```text
target modes:
  factor,pnl

group spec:
  direction,combined_regime,session_regime

target:
  is_large_loss

fold:
  train = selected rows with month < target month
```

## Score Summary

| mode | feature set | AUC | average precision | Brier | pred mean | model used rate |
|---|---|---:|---:|---:|---:|---:|
| pnl | base | `0.6682` | `0.2146` | `0.0913` | `0.0552` | `0.7155` |
| factor | base | `0.6741` | `0.1714` | `0.0923` | `0.0535` | `0.7155` |
| pnl | base_prior | `0.6565` | `0.1604` | `0.0948` | `0.0590` | `0.7155` |
| factor | base_prior | `0.6628` | `0.1532` | `0.0945` | `0.0539` | `0.7155` |

Reading:

- baseはAUCだけなら `0.67` 付近で、large-loss識別に少し情報がある。
- prior pressureを足すとAUC/AP/Brierが全て悪化する。
- prior residual pressureは現形ではlarge-loss headの改善featureになっていない。

## Threshold Diagnostics

Top rows sorted by no-replacement delta:

| mode | feature set | threshold | flagged trades | flagged PnL | kept PnL | delta | flagged large losses | large-loss recall |
|---|---|---|---:|---:|---:|---:|---:|---:|
| factor | base_prior | `prob_ge_0.4` | `2` | `+15.0000` | `+314.4348` | `-15.0000` | `0` | `0.0000` |
| factor | base_prior | `prob_ge_0.3` | `7` | `+23.4124` | `+306.0224` | `-23.4124` | `1` | `0.0435` |
| factor | base | `prob_ge_0.4` | `3` | `+25.8100` | `+303.6248` | `-25.8100` | `0` | `0.0000` |
| factor | base_prior | `top_q95` | `13` | `+39.8504` | `+289.5844` | `-39.8504` | `1` | `0.0435` |
| pnl | base | `prob_ge_0.2` | `17` | `+58.1320` | `+271.3028` | `-58.1320` | `5` | `0.2174` |

Reading:

- high-risk removal never improves total.
- Some thresholds capture large losses, but they capture even larger winners.
- This confirms again that pointwise risk head score cannot be used as a direct admission gate.

## Failure Pattern

Top predicted risk rows include large winners:

| mode | feature set | month | context | adjusted PnL | large loss | predicted risk | prior pressure |
|---|---|---|---|---:|---:|---:|---:|
| pnl | base | `2025-11` | `short|down_normal_vol|london` | `-7.9800` | true | `0.6541` | `29.9639` |
| pnl | base | `2025-11` | `short|down_normal_vol|london` | `+62.0800` | false | `0.6359` | `29.9639` |
| pnl | base_prior | `2025-11` | `long|range_normal_vol|ny_late` | `+0.1200` | false | `0.5306` | `0.0000` |
| pnl | base_prior | `2025-11` | `short|down_normal_vol|london` | `-7.9800` | true | `0.5004` | `29.9639` |
| pnl | base_prior | `2025-11` | `short|down_normal_vol|london` | `+62.0800` | false | `0.5004` | `29.9639` |

Reading:

- The model recognizes risky context, but that context contains both a large loss and a larger winner.
- Without a replacement / path-aware decision layer, high-risk pointwise blocking removes too much upside.
- This is an execution-decision problem, not just a classifier problem.

## Decision

Accepted:

- chronological large-loss head diagnostic infrastructure
- base vs base+prior feature comparison
- threshold summary as negative admission evidence

Rejected:

- prior residual pressure as currently defined as a large-loss head improvement feature
- large-loss probability as direct hard gate
- high-risk quantile removal as standard policy

Standard policy remains NoTrade.

## Next

1. Do not add more pointwise hard gates on selected trades.
2. If using large-loss probability, feed it into candidate-level selector / stateful replay, not direct removal.
3. Consider path-aware labels that distinguish "large loss with no subsequent winner in same risky context" from "risky context with high upside".
4. Keep role/month floor and NoTrade-first admission as the standard gate.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_trade_large_loss_head.py tests/test_entry_ev_selected_trade_large_loss_head.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_large_loss_head`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_large_loss_head tests.test_entry_ev_selected_trade_prior_residual_pressure tests.test_docs_reports`: OK
- `git diff --check`: OK
- prior pressure large-loss head run: OK
