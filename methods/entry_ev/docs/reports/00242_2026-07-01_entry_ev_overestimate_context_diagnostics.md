# Entry EV Overestimate Context Diagnostics

日時: 2026-07-01 08:04 JST
更新日時: 2026-07-01 08:04 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00241で「EV overestimate riskはfresh損失を拾うがrefit勝ちも削る」と分かったため、high-risk rowsをside/contextで分解する `scripts/experiments/entry_ev_overestimate_context_diagnostics.py` を追加した。
- contextは `direction`, `support_bucket`, `pressure_bucket`, `prior_support_bucket`, `feature_pressure_bucket`, `side_drift_bucket`。
- high-riskの損失は一枚岩ではない。最悪contextは `long/missing/low/missing/low/negative` で 6 rows / `-83.0680`、全てhigh-risk。
- 一方、`short/missing/low/missing/low/negative` は high-riskで `+89.2040`。ここをhard blockするとrefit勝ちを壊す。
- 判断: EV overestimate riskはside/context付きfeatureとして有用。ただし削除gateではなく、side/context別のranking/calibration headへ回す。

## Artifacts

- Script: `scripts/experiments/entry_ev_overestimate_context_diagnostics.py`
- Test: `tests/test_entry_ev_overestimate_context_diagnostics.py`
- Input:
  - `data/reports/backtests/20260630_145606_20260630_entry_ev_composite_target_decomposition_s1/component_trade_targets.csv`
- Diagnostic artifact:
  - `data/reports/backtests/20260630_230353_20260701_entry_ev_overestimate_context_diagnostics_s1/`

Outputs:

```text
ev_overestimate_context_trades.csv
role_context_ev_overestimate_summary.csv
context_ev_overestimate_summary.csv
candidate_context_ev_overestimate_summary.csv
role_context_high_risk_contrast.csv
config.json
```

## Method

The EV-overestimate risk is the same chronological prior feature as 00241:

```text
target = executable_ev_overestimate_target
group_columns = support_bucket, pressure_bucket
risk_threshold = 0.50
prior_strength = 5
min_group_support = 3
```

Additional context buckets:

```text
prior_support_bucket:
  missing <=0, low <=0.2, medium <=0.5, high >0.5

feature_pressure_bucket:
  low <0.25, medium <0.5, high <0.7, extreme >=0.7

side_drift_bucket:
  negative <= -0.05, positive >= 0.05, otherwise neutral
```

This is a diagnostic decomposition. It does not select a policy and does not simulate stateful replacement.

## Worst Contexts

| direction | support | pressure | prior support | feature pressure | side drift | rows | total | target rate | pred risk | high-risk rows | high-risk pnl |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| long | missing | low | missing | low | negative | `6` | `-83.0680` | `0.6667` | `0.6603` | `6` | `-83.0680` |
| short | medium | high | medium | medium | neutral | `1` | `-32.0364` | `1.0000` | `0.5942` | `1` | `-32.0364` |
| long | medium | extreme | medium | high | positive | `2` | `-28.5600` | `1.0000` | `0.5357` | `2` | `-28.5600` |
| long | missing | low | missing | low | neutral | `42` | `-10.1132` | `0.7143` | `0.6224` | `4` | `-17.5684` |
| short | missing | low | missing | low | neutral | `23` | `-13.8470` | `0.5217` | `0.6267` | `4` | `-11.6174` |
| long | high | extreme | high | high | negative | `4` | `-29.5056` | `1.0000` | `0.2679` | `0` | `0.0000` |

The last row is important: not all EV-overestimate target losses are caught by this risk feature. Low predicted risk can still be bad when context differs.

## Role Contrast

| context | fresh high-risk pnl | refit high-risk pnl | cal high-risk pnl | reading |
|---|---:|---:|---:|---|
| short / missing / low / missing / low / negative | `0.0000` | `+89.2040` | `0.0000` | high-risk but strongly profitable in refit |
| long / missing / low / missing / low / negative | `-66.9840` | `0.0000` | `-16.0840` | high-risk and broadly bad |
| short / medium / high / medium / medium / neutral | `-32.0364` | `0.0000` | `0.0000` | fresh-specific loss, tiny support |
| long / high / medium / high / medium / positive | `0.0000` | `+23.5500` | `0.0000` | high-risk but profitable |
| long / missing / low / missing / low / positive | `0.0000` | `+23.4200` | `0.0000` | high-risk but profitable |
| short / missing / low / missing / low / neutral | `-11.6054` | `-0.0120` | `0.0000` | mild broad loss |

The same `missing/low` risk bucket has opposite behavior by direction and side drift:

- long + negative drift: bad
- short + negative drift: strongly profitable in refit
- long/short neutral: weakly bad
- positive drift variants can be profitable

## Decision

Accepted:

- EV-overestimate risk context decomposition.
- `direction + support/pressure + prior support + feature pressure + side drift` as candidate features for the next ranking/calibration head.
- Role contrast table as a guard against turning high-risk into a hard blocker.

Not accepted:

- Any context hard block from this report.
- Treating `missing/low` as uniformly bad.
- Treating EV-overestimate target risk as sufficient without side/context.

Standard policy remains NoTrade.

## Next

1. Use `direction`, `side_drift_bucket`, `prior_support_bucket`, and `feature_pressure_bucket` as low-capacity interaction features for EV-overestimate calibration.
2. For ranking, penalize high-risk only when the context resembles historically bad contexts; do not penalize all high-risk rows.
3. Add stateful replay before any pointwise context screen is considered.
4. Increase chronological component-target coverage so `missing/low` no-prior effects are not overread.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_overestimate_context_diagnostics.py tests/test_entry_ev_overestimate_context_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_overestimate_context_diagnostics`: OK
- Context diagnostic run: OK
