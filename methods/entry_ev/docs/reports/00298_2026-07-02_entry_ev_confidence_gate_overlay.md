# Entry EV Confidence Gate Overlay

日時: 2026-07-02 14:31 JST
更新日時: 2026-07-02 14:31 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00297の次アクションとして、thin-support residual monthsを月内順序削除ではなくモデル出力confidenceで説明できるか診断した。
- `scripts/experiments/entry_ev_confidence_gate_overlay.py` を追加し、既存entry-block overlay trade pathへ観測可能なconfidence gateをno-replacementで重ねられるようにした。
- 対象は00296 diagnostic benchmark branchに絞った。
- `taken_ev_ge10` は month minを `-0.7200 -> 0.0000` へ上げるが、totalは `+329.4348 -> +36.0280`、tradesは `232 -> 111` へ落ち、standard blockersは `role_trades_low,month_trades_low`。これはNoTradeに近い低活動化であり、標準候補ではない。
- その他のrank/side-gap/loss-prob/fixed-horizon confidence gateはmonth floorやrole floorを悪化させた。
- 判断: confidence gate overlay diagnosticsはaccepted infrastructure。現confidence hard gateはreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_confidence_gate_overlay.py`
- New test:
  - `tests/test_entry_ev_confidence_gate_overlay.py`
- Confidence gate overlay run:
  - `data/reports/backtests/20260702_053041_20260702_entry_ev_confidence_gate_overlay_residual_combo_best_s1/`
- Support-aware check:
  - `data/reports/backtests/20260702_053056_20260702_entry_ev_confidence_gate_support_aware_best_s1/`

## Target Branch

```text
selector_variant:
  loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny
candidate:
  q95_sg95_rank90_floor5_side_regime_session_month
```

Baseline: total `+329.4348`, role min `+0.5354`, month min `-0.7200`, trades `232`.

## Results

Top selection rows:

| rule | total | delta vs input | month min | role min | trades | blocked trades | blocked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `taken_ev_ge10` | `+36.0280` | `-293.4068` | `+0.0000` | `+0.0000` | `111` | `121` | `+293.4068` |
| `none` | `+329.4348` | `+0.0000` | `-0.7200` | `+0.5354` | `232` | `0` | `+0.0000` |
| `rank_ge0p55` | `+319.0304` | `-10.4044` | `-1.4806` | `-1.4806` | `172` | `60` | `+10.4044` |
| `lossprob_le0p40` | `+280.0334` | `-49.4014` | `-1.7512` | `+0.5634` | `158` | `74` | `+49.4014` |
| `rank_ge0p55_sidegap_ge0p10` | `+237.7848` | `-91.6500` | `-2.0040` | `-0.1760` | `119` | `113` | `+91.6500` |
| `sidegap_ge0` | `+293.4376` | `-35.9972` | `-4.9244` | `+0.8334` | `199` | `33` | `+35.9972` |
| `fixed720_pred_ge0` | `+221.2556` | `-108.1792` | `-9.5402` | `+0.4400` | `166` | `66` | `+108.1792` |

Support-aware check:

| rule | diagnostic status | support-aware pass | total | role min | month min | strict blockers |
|---|---|---:|---:|---:|---:|---|
| `none` | `support_aware_only` | `true` | `+329.4348` | `+0.5354` | `-0.7200` | `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` |
| `taken_ev_ge10` | `support_aware_only` | `true` | `+36.0280` | `+0.0000` | `+0.0000` | `role_trades_low,month_trades_low` |
| `rank_ge0p60` | `support_aware_only` | `true` | `+122.0200` | `+0.0000` | `-4.6800` | `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` |
| `rank_ge0p65` | `support_aware_only` | `true` | `+68.5990` | `+0.0000` | `-16.3280` | `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` |
| `sidegap_ge0p10` | `blocked` | `false` | `+240.7698` | `+1.3940` | `-5.2644` | `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` |

No rule passed the standard gate.

## Feature Bins

The confidence features are not monotonic enough to justify direct hard gates:

| feature | useful observation |
|---|---|
| `pred_taken_ev` | Low bins are better: bin0 `+107.8948`, bin1 `+139.7534`, top bin only `+3.9402`. High predicted EV is not a reliable high-quality subset. |
| `pred_taken_entry_local_rank` | Best bin is not the highest-only region: bin1 `+149.6422`, bin4 `+122.0200`, middle bins weak. |
| `pred_side_confidence_gap` | Higher side-gap helps some bins but is not a floor solution; `sidegap_ge0` worsens month min to `-4.9244`. |
| `selected_loss_first_prob` | Low loss-prob bins are strong, but `lossprob_le0p30/0p35/0p40` still fail month floor/support-aware blockers. |
| fixed-horizon predicted PnL | Positive predicted fixed-horizon PnL does not map cleanly to realized floor improvement. |

## Decision

Accepted:

- confidence gate overlay diagnostics
- feature-bin diagnostics for selected trade confidence calibration
- support-aware check for confidence-gated variants

Rejected:

- direct `pred_taken_ev` hard gate as a standard policy
- direct rank / side-gap / loss-prob / fixed-horizon confidence hard gates as standard policy
- treating `taken_ev_ge10` floor `0.0` as improvement, because it is mostly low-activity/NoTrade-like and fails support

Standard policy remains NoTrade.

## Next

1. Confidence features should feed calibration/model diagnostics, not direct hard gates.
2. The next useful direction is chronological calibration of expected PnL or uncertainty, not same-window threshold selection.
3. Keep NoTrade-first standard gate unchanged.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_confidence_gate_overlay.py tests/test_entry_ev_confidence_gate_overlay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_confidence_gate_overlay`: OK
- confidence gate overlay run: OK
- support-aware check run: OK
