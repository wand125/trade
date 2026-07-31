# Entry EV Side Balance Downside Selector

日時: 2026-06-30 19:32 JST
更新日時: 2026-06-30 19:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00235の次アクションとして、side-balance/downside interactionを個別trade hard gateではなくcandidate-level selector featureとして集約する `scripts/experiments/entry_ev_side_balance_downside_selector.py` を追加した。
- `prior_downside_risk_score >= 0.20` と `side_balance_downside_interaction_score >= 0.005` のshare、prior support zero share、feature pressure score、uncovered loss PnLをrole/month/candidate単位で集計する。
- strict NoTrade-first gateでは全候補が不合格。これは00220以降の結論と整合する。
- 診断用にrole/month PnL floorを緩めるとfloor10系が残り、feature pressureは低い。ただしこれは「低リスク候補」ではなく、fresh roleがなく prior zero share が `0.90` 以上の薄い候補である。
- floor5系はfresh tailを含むため、risk/intersection pressureが高い。q95 floor5は `risk_high_share 0.2642`, `interaction_high_share 0.3396`, `feature_pressure 0.3116`, uncovered loss `-153.0528`。
- 判断: candidate-level aggregationはaccepted。side-balance/downside selector feature単独では標準採用しない。次は「低pressureだがcoverage不足」の候補を採用しないため、support/coverage featureと一緒に使う。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_balance_downside_selector.py`
- Test: `tests/test_entry_ev_side_balance_downside_selector.py`
- Strict selector diagnostics:
  - `data/reports/backtests/20260630_103209_20260630_entry_ev_side_balance_downside_selector_strict_s1/`
- Relaxed diagnostic selector:
  - `data/reports/backtests/20260630_103224_20260630_entry_ev_side_balance_downside_selector_relaxed_s1/`
- Input:
  - `data/reports/backtests/20260630_101914_20260630_entry_ev_side_balance_downside_interaction_s1/enriched_side_balance_downside_trades.csv`

## Method

Candidate-level feature aggregation:

```text
risk_high_share = share(prior_downside_risk_score >= 0.20)
interaction_high_share = share(side_balance_downside_interaction_score >= 0.005)
prior_zero_share = share(prior_trade_count <= 0)

feature_pressure_score =
  0.35 * risk_high_share
  + 0.30 * interaction_high_share
  + 0.20 * clip(risk_mean, 0, 1)
  + 0.15 * prior_zero_share
```

`uncovered_loss_pnl` is diagnostic only:

```text
loss trade where prior_zero OR risk below threshold OR interaction below threshold
```

This column uses realized PnL and must not become an entry-time feature. It is used to detect whether the feature family fails to cover losses.

## Strict Selector

Strict gate:

```text
roles = cal2024_calibration_validation, fresh2024_validation, refit2025_validation
min positive roles = 3
min total PnL = 0
min role total PnL = 0
min month PnL = 0
```

| candidate | eligible | blockers | total | min role | min month | trades | risk high | interaction high | prior zero | pressure | uncovered loss |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| q99 floor10 | false | roles/positive/active/role/month | `+1.1920` | `-7.3764` | `-7.3764` | `10` | `0.1000` | `0.1000` | `0.9000` | `0.2040` | `-7.2516` |
| q95 floor10 | false | roles/positive/active/role/month | `+15.5736` | `-11.2600` | `-9.4600` | `23` | `0.0870` | `0.0870` | `0.9130` | `0.2009` | `-50.0040` |
| q99 floor5 | false | positive/total/role/month | `-10.2286` | `-38.3550` | `-35.7120` | `29` | `0.2414` | `0.3448` | `0.6207` | `0.3001` | `-69.0312` |
| q95 floor5 | false | positive/role/month | `+14.6138` | `-82.2428` | `-46.5308` | `53` | `0.2642` | `0.3396` | `0.6226` | `0.3116` | `-153.0528` |

Result: NoTrade.

## Relaxed Diagnostic

Relaxed diagnostic gate:

```text
min roles = 2
min positive roles = 1
min role total PnL >= -15
min month PnL >= -10
```

This is not a standard-selection gate. It is used only to see what the feature family prefers when strict robustness is relaxed.

Result:

- `q99 floor10` and `q95 floor10` become eligible.
- Feature grid has 320 rows; 128 select `q99 floor10`, 192 remain NoTrade.
- `q99 floor10` is preferred because min role `-7.3764` is less bad than q95 floor10 `-11.2600`, despite q95 floor10 having higher total PnL.

This is not a promotion signal. Both floor10 candidates have only two active roles and prior zero share around `0.90`, meaning they look low-pressure partly because there is too little prior evidence and no fresh role coverage.

## Worst Role-Month Coverage

| candidate | role | month | trades | pnl | risk high | interaction high | prior zero | pressure | uncovered loss |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| q95 floor5 | fresh2024 | 2024-03 | `6` | `-46.5308` | `0.5000` | `0.5000` | `0.3333` | `0.4132` | `-45.5448` |
| q95 floor5 | fresh2024 | 2024-04 | `2` | `-35.7120` | `0.5000` | `0.5000` | `0.5000` | `0.4457` | `-33.4920` |
| q99 floor5 | fresh2024 | 2024-04 | `2` | `-35.7120` | `0.5000` | `0.5000` | `0.5000` | `0.4457` | `-33.4920` |
| q95 floor10 | cal2024 | 2024-01 | `20` | `-9.4600` | `0.0000` | `0.0000` | `1.0000` | `0.1500` | `-48.2040` |

The feature family explains part of the floor5 fresh tail, but it also shows a major weakness: prior-zero losses can have low risk/interaction pressure and still be large.

## Decision

Accepted:

- Candidate-level side-balance/downside feature aggregation.
- Feature pressure score as a low-capacity diagnostic/ranking feature.
- Prior-zero share and uncovered-loss diagnostics as coverage warnings.
- Strict and relaxed selector artifacts.

Not accepted:

- Promoting floor10 candidates from the relaxed diagnostic.
- Using low feature pressure alone as a candidate-selection rule.
- Using `uncovered_loss_pnl` as a model feature.

Standard policy remains NoTrade.

## Next

1. Add coverage constraints to future selector features: prior zero share, active role count, and fresh-role coverage must be considered together with pressure score.
2. Use side-balance/downside pressure as a negative ranking feature only after support is adequate.
3. Build a replacement-aware diagnostic before treating candidate-level feature pressure as a stateful policy edge.
4. For model training, use pressure score as one feature among executable EV, exit capture, direction-side inversion, and side-balance drift; do not let it dominate.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_balance_downside_selector.py tests/test_entry_ev_side_balance_downside_selector.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_balance_downside_selector`: OK
- Strict selector diagnostics: OK
- Relaxed selector diagnostics: OK
