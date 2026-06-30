# Entry EV Side Balance Feature Diagnostics

日時: 2026-06-30 19:08 JST
更新日時: 2026-06-30 19:08 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00233の反省に沿って、side-balance driftをdirect score multiplierではなくselected-trade featureとして診断する `scripts/experiments/entry_ev_side_balance_feature_diagnostics.py` を追加した。
- 00233と同じ validation 6ヶ月 / candidates / profit `1.00` / loss `1.20` / max hold `720m` を `--write-trades` 付きで再実行し、trade単位でprediction side-balance列を再結合した。
- selected sideがprior drift上で過剰側か、underrepresented側か、abs driftが大きいかを閾値別にpost-hocで集計した。
- 結論: side-balance drift単体はselector/ranking featureとしてもまだ弱い。q99系では一部post-hoc screenが損失を拾うが、q95系では同じ系のscreenが利益を大きく削る。
- したがって、side-balance driftは単独gateにしない。prior side PnL、direction error、exit capture failure、context loss、realized executable EVと組み合わせたdownside-conditioned featureとして扱う。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_balance_feature_diagnostics.py`
- Test: `tests/test_entry_ev_side_balance_feature_diagnostics.py`
- Validation backtest with trades:
  - `data/reports/backtests/20260630_100703_20260630_entry_ev_side_balance_dense720_policy_backtest_s1_trades_validation_months/`
- Feature diagnostics:
  - `data/reports/backtests/20260630_100834_20260630_entry_ev_side_balance_feature_diagnostics_s1_clean/`
- Input side-balanced predictions:
  - `data/reports/backtests/20260630_095101_20260630_entry_ev_side_balance_dense720_inputs_s1/enriched_predictions/`

## Method

Trade feature definitions:

```text
drift = pred_side_balance_long_share_drift

if selected direction == long:
  signed_drift_for_trade = drift
  taken_scale = pred_side_balance_long_scale

if selected direction == short:
  signed_drift_for_trade = -drift
  taken_scale = pred_side_balance_short_scale

selected_side_overrepresented = signed_drift_for_trade > 0
selected_side_underrepresented = signed_drift_for_trade < 0
taken_penalty = 1 - taken_scale
```

Screen effects are pointwise diagnostics only:

```text
kept_total_pnl = total PnL after removing flagged selected trades
pointwise_delta_if_removed = kept_total_pnl - original_total_pnl
```

This does not model one-position replacement trades, so it is not a promotion rule.

## Role Feature Summary

| role | candidate | trades | total | abs drift | overrep share | underrep share | taken penalty |
|---|---|---:|---:|---:|---:|---:|---:|
| fresh2024 | q95 floor5 | `8` | `-82.2428` | `0.0644` | `0.3750` | `0.6250` | `0.0196` |
| fresh2024 | q99 floor5 | `6` | `-38.3550` | `0.0816` | `0.3333` | `0.6667` | `0.0240` |
| cal2024 | q95 floor10 | `21` | `-11.2600` | `0.0087` | `0.0476` | `0.0000` | `0.0087` |
| refit2025 | q99 floor10 | `1` | `-7.3764` | `0.0637` | `0.0000` | `1.0000` | `0.0000` |
| cal2024 | q99 floor5 | `13` | `-2.1072` | `0.0648` | `0.0769` | `0.2308` | `0.0141` |
| cal2024 | q95 floor5 | `26` | `+2.8654` | `0.0462` | `0.0385` | `0.1923` | `0.0070` |
| refit2025 | q99 floor5 | `10` | `+30.2336` | `0.1024` | `0.5000` | `0.5000` | `0.0598` |
| refit2025 | q95 floor5 | `19` | `+93.9912` | `0.0973` | `0.4737` | `0.5263` | `0.0567` |

Important observation: winning refit q95/q99 has higher abs drift and overrep share than losing fresh q95/q99. Therefore "high drift" or "selected side overrepresented" cannot be used as a generic blocker.

## Pointwise Screens

Best-looking post-hoc screens:

| candidate | screen | threshold | removed trades | removed pnl | kept total | kept min role | delta |
|---|---|---:|---:|---:|---:|---:|---:|
| q99 floor5 | selected_underrepresented | `0.02` | `11` | `-16.8394` | `+6.6108` | `+1.6420` | `+16.8394` |
| q99 floor5 | abs_drift_high | `0.02` | `18` | `-14.7424` | `+4.5138` | `+0.2980` | `+14.7424` |
| q99 floor10 | abs_drift_high | `0.02` | `2` | `-9.1764` | `+10.3684` | `+10.3684` | `+9.1764` |
| q99 floor10 | abs_drift_high | `0.05` | `2` | `-9.1764` | `+10.3684` | `+10.3684` | `+9.1764` |
| q95 floor10 | abs_drift_high | `0.05` | `2` | `-9.1764` | `+24.7500` | `-9.4600` | `+9.1764` |

But the same idea fails on q95 floor5:

| candidate | screen | threshold | removed trades | removed pnl | kept total | kept min role | delta |
|---|---|---:|---:|---:|---:|---:|---:|
| q95 floor5 | selected_underrepresented | `0.05` | `14` | `+14.0236` | `+0.5902` | `-43.4828` | `-14.0236` |
| q95 floor5 | selected_overrepresented | `0.10` | `8` | `+23.2710` | `-8.6572` | `-84.6728` | `-23.2710` |
| q95 floor5 | selected_overrepresented | `0.05` | `10` | `+35.3140` | `-20.7002` | `-84.6728` | `-35.3140` |
| q95 floor5 | abs_drift_high | `0.05` | `24` | `+49.3376` | `-34.7238` | `-45.9128` | `-49.3376` |

So side-balance drift can describe some q99 losses, but it is not stable enough to rank or block q95 candidates.

## Worst Trade Contexts

The largest fresh losses show why generic drift rules fail:

| role | candidate | side | context | pnl | signed drift | overrepresented |
|---|---|---|---|---:|---:|---|
| fresh2024 | q95/q99 floor5 | long | `range_low_vol/london` | `-33.4920` | `-0.1400` | false |
| fresh2024 | q95 floor5 | short | `range_low_vol/london` | `-32.0364` | `+0.0131` | true |
| fresh2024 | q95 floor5 | short | `range_low_vol/asia` | `-13.5084` | `-0.0125` | false |
| refit2025 | q95/q99 floor5 | long | `up_low_vol/ny_overlap` | `-14.2800` | `+0.1761` | true |

The biggest fresh long loss is underrepresented by the side-balance signal and receives no direct penalty. The biggest fresh short loss is overrepresented but has drift only `+0.0131`, below the useful thresholds. This explains why direct side-balance penalty and simple feature screens cannot reliably remove the tail.

## Decision

Accepted:

- Side-balance selected-trade feature diagnostics.
- `side_balance_signed_drift_for_trade`.
- `side_balance_selected_side_overrepresented` / `underrepresented`.
- `side_balance_taken_scale` / `taken_penalty`.
- Pointwise screen-effect table as a diagnostic only.

Not accepted:

- Generic `selected_side_overrepresented` blocker.
- Generic `abs_drift_high` blocker.
- Generic `selected_underrepresented` blocker.
- Promotion of q99 pointwise screens without stateful replacement backtest and more validation windows.

Standard policy remains NoTrade.

## Next

1. Combine side-balance drift with prior downside evidence: side PnL, direction error, exit capture failure, context loss, and realized executable EV.
2. Prefer a low-capacity ranking/selector feature over a hard trade blocker.
3. If a screen is tested dynamically, pre-register q99-only and q95-only variants separately; do not reuse one threshold family across both.
4. Keep the current NoTrade-first gates and do not promote pointwise improvements without stateful replacement simulation.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_balance_feature_diagnostics.py tests/test_entry_ev_side_balance_feature_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_balance_feature_diagnostics`: OK
- Validation backtest with `--write-trades`: OK
- Side-balance feature diagnostics: OK
