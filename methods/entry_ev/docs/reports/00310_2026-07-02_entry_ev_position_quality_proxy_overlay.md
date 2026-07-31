# Entry EV Position-Quality Proxy Overlay

日時: 2026-07-02 17:22 JST
更新日時: 2026-07-02 17:22 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00309の次アクションとして、`holdext_long_range_normal_ny` をextension vetoではなく、entry-time observableなposition-quality proxyとして検証した。
- `scripts/experiments/entry_ev_stateful_entry_block_overlay.py` に long / `range_normal_vol` / `ny_overlap` 系のentry block rulesを追加した。
- 対象branchは00308/00309の `isolated_large_loss_long / threshold -5 / fixed720 / require-model-used`。
- `long_range_normal_ny_fixed60_pred_gt0` は total `+326.1098 -> +337.6010`、month min `-0.8832 -> -0.7200` まで改善した。
- ただしblocked 4件は全て `refit2025_validation` に集中し、standard admissionは `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` で不合格。
- default support-awareでは `support_aware_only` だが、support2では `too_many_support_limited_negative_months`、shallow025では `structural_negative_months` でblocked。
- 判断: entry-time position-quality proxy rulesはdiagnostic infrastructureとしてaccepted。`long_range_normal_ny_fixed60_pred_gt0` はdiagnostic candidateに留め、標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_stateful_entry_block_overlay.py`
- Updated tests:
  - `tests/test_entry_ev_stateful_entry_block_overlay.py`
- Proxy overlay:
  - `data/reports/backtests/20260702_082037_20260702_entry_ev_00310_position_quality_proxy_overlay_s1/`
- Support-aware admission:
  - default: `data/reports/backtests/20260702_082112_20260702_entry_ev_00310_position_quality_support_aware_default_s1/`
  - support2: `data/reports/backtests/20260702_082112_20260702_entry_ev_00310_position_quality_support_aware_support2_s1/`
  - shallow025: `data/reports/backtests/20260702_082112_20260702_entry_ev_00310_position_quality_support_aware_shallow025_s1/`

## Method

00309のnegative result:

```text
post-hold block: trade全体を削除すると改善
extension veto: base exitへ戻すと悪化
```

このため、対象rowはexit extensionの失敗ではなく、entry/no-entryまたはposition-quality問題として扱う。

追加したentry-time observable rules:

```text
long_range_normal_ny
long_range_normal_ny_fixed60_pred_gt0
long_range_normal_ny_fixed720_pred_gt0
long_range_normal_ny_rank_lt0p55
long_range_normal_ny_taken_ev_lt8
long_range_normal_ny_lossprob_ge0p28
long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2
```

いずれも `direction`, `combined_regime`, `session_regime`, `selected_loss_first_prob`, `pred_side_confidence_gap`, `pred_taken_entry_local_rank`, `pred_taken_ev`, `selected_fixed_*m_pred_pnl` だけを使う。actual fixed-horizon PnLや `exit_capture_ratio` は診断表示に留め、rule条件には使わない。

## Overlay Result

対象: `isolated_large_loss_long / threshold -5 / fixed720`

| entry block rule | total | delta | blocked | blocked PnL | month min | role min | trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| `long_range_normal_ny` | `+342.1610` | `+16.0512` | `11` | `-16.0512` | `-0.9692` | `+0.5354` | `235` |
| `long_range_normal_ny_rank_lt0p55` | `+341.0280` | `+14.9182` | `8` | `-14.9182` | `-0.9430` | `+0.5354` | `238` |
| `long_range_normal_ny_lossprob_ge0p28` | `+338.6138` | `+12.5040` | `9` | `-12.5040` | `-0.9692` | `+0.5354` | `237` |
| `long_range_normal_ny_taken_ev_lt8` | `+338.4186` | `+12.3088` | `7` | `-12.3088` | `-0.9430` | `+0.5354` | `239` |
| `long_range_normal_ny_fixed720_pred_gt0` | `+338.3276` | `+12.2178` | `8` | `-12.2178` | `-0.9692` | `+0.5354` | `238` |
| `long_range_normal_ny_fixed60_pred_gt0` | `+337.6010` | `+11.4912` | `4` | `-11.4912` | `-0.7200` | `+0.5354` | `242` |
| `holdext_long_range_normal_ny` | `+326.9930` | `+0.8832` | `1` | `-0.8832` | `-0.7200` | `+0.5354` | `245` |
| `long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2` | `+326.9930` | `+0.8832` | `1` | `-0.8832` | `-0.7200` | `+0.5354` | `245` |
| `none` | `+326.1098` | `+0.0000` | `0` | `+0.0000` | `-0.8832` | `+0.5354` | `246` |

Reading:

- totalだけなら broad `long_range_normal_ny` block が最大だが、month floorは `-0.9692` へ悪化する。
- `long_range_normal_ny_fixed60_pred_gt0` は totalを大きく改善しながらmonth minを `-0.7200` に保つため、今回の最良診断候補。
- `long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2` は00309のtarget row 1件だけをentry-time featuresで再現するが、1件proxyとして過学習リスクが高い。

## Blocked Rows

`long_range_normal_ny_fixed60_pred_gt0` が削った4件:

| role | month | entry | PnL after hold | base PnL | fixed60 pred | fixed60 actual | loss prob | side gap | taken EV |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `refit2025_validation` | `2025-12` | `2025-12-01 15:06+00:00` | `-7.5480` | `-7.5480` | `+0.5132` | `-9.6960` | `0.2999` | `0.0738` | `5.3797` |
| `refit2025_validation` | `2025-10` | `2025-10-09 16:22+00:00` | `-2.9880` | `-2.9880` | `+0.9762` | `-8.3520` | `0.3033` | `0.1519` | `7.6383` |
| `refit2025_validation` | `2025-08` | `2025-08-07 15:43+00:00` | `-0.8832` | `-2.5152` | `+1.3580` | `-2.0160` | `0.2791` | `0.2674` | `7.1580` |
| `refit2025_validation` | `2025-12` | `2025-12-01 16:03+00:00` | `-0.0720` | `-0.0720` | `+1.2409` | `-10.1880` | `0.3400` | `0.2949` | `5.2597` |

Reading:

- 全て `refit2025_validation` の `long / range_normal_vol / ny_overlap` に集中している。
- predicted fixed60がpositiveなのにactual fixed60が大きくnegativeという、短期path過大評価の形は一貫している。
- しかし未使用chronologyや別familyでの再現がなく、標準化には足りない。

## Support-Aware Admission

`long_range_normal_ny_fixed60_pred_gt0`:

| check | status | total | month min | negative months | support-limited neg | shallow neg | structural neg | blocker |
|---|---|---:|---:|---:|---:|---:|---:|---|
| standard | blocked | `+337.6010` | `-0.7200` | `4` | `3` | `1` | `0` | month/role/month-trade/side-share |
| default support-aware | `support_aware_only` | `+337.6010` | `-0.7200` | `4` | `3` | `1` | `0` | none |
| support2 | blocked | `+337.6010` | `-0.7200` | `4` | `3` | `1` | `0` | too many support-limited negative months |
| shallow025 | blocked | `+337.6010` | `-0.7200` | `4` | `3` | `0` | `1` | structural negative months |

Reading:

- 00295/00296と同じく、default support-aware passだけでは標準採用しない。
- support-limited月が3つ残るため、許容を2へ締めると落ちる。
- shallow floorを `-0.25` に締めると構造的negative monthが出る。

## Decision

Accepted:

- entry-time observableな `long_range_normal_ny*` position-quality proxy rules
- support-aware default/support2/shallow025をentry-block overlay候補にも必ず併記する運用
- fixed-horizon predicted PnLとactual PnLの乖離を短期path過大評価診断として見ること

Diagnostic candidate:

- `long_range_normal_ny_fixed60_pred_gt0`

Rejected:

- `long_range_normal_ny` broad blockをtotal改善だけで標準化すること
- 1件だけを拾う `long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2` を標準policyとして扱うこと
- default `support_aware_only` を標準admissionとして扱うこと
- refit2025に集中したrow削除を未使用chronologyなしで採用すること

Standard policy remains NoTrade.

## Next

1. `long_range_normal_ny_fixed60_pred_gt0` を未使用chronologyに再探索なしで適用できる形にする。
2. fixed60 positive but actual short-horizon negative のパターンを、post-hoc actualではなく事前予測可能な uncertainty / calibration residual featureへ戻す。
3. refit2025集中を避けるため、family別・role別に同じentry-time proxyが再現するか確認する。
4. 引き続き短期path過大評価はhard blockではなく、candidate selector / calibration / exit timing targetのfeature候補として扱う。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_stateful_entry_block_overlay.py tests/test_entry_ev_stateful_entry_block_overlay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_stateful_entry_block_overlay tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00310 position-quality proxy overlay run: OK
- 00310 support-aware default/support2/shallow025 runs: OK
