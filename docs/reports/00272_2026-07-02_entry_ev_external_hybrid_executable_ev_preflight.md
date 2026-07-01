# Entry EV External Hybrid Executable EV Preflight

日時: 2026-07-02 08:04 JST
更新日時: 2026-07-02 08:04 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00271で確認したEV過大評価 / exit-capture failureに対し、既存のprior-only executable EV補正を外部hybrid `2025-09..12` に固定適用した。
- prior capture factorは00229/00231系と同じ `20260630_084006_entry_ev_exit_capture_targets_validation_q95q99_thr020/enriched_exit_capture_targets.csv` を使った。
- まずpost-selector score `pred_exit_regret_selector_replguard_preblockgap_confidenceexit_bucket_t0p4_*` に capture factorを掛け、`external_executable` quantile列を生成した。
- score scaleは大きく縮んだ。base selected score q95は `31.6282..37.7288` から executable q95 `9.1734..12.4031` へ低下した。
- ただしstateful replayは改善しない。q99は `-27.5640`, 3 trades、q95は `-29.5080`, 4 trades。NoTrade-first admissionは両方NoTrade。
- 補正後trade enrichmentではq99/q95ともwin rate `0.0`。良いtradeも削り、悪い少数tradeが残った。
- 判断: executable EV補正インフラは有用だが、post-selector / blocked-side scoreへ後段適用するのは採用しない。次はselector前のbase scoreへcapture factorを入れ、その後にexit-regret selector / side-gap quantileを再計算する。

## Artifacts

- Executable input:
  - `data/reports/backtests/20260701_230307_20260702_entry_ev_external_hybrid_2025_0912_executable_inputs_s1/`
- Stateful replay:
  - `data/reports/backtests/20260701_230321_20260702_entry_ev_external_hybrid_2025_0912_executable_replay_s1/`
- Admission:
  - `data/reports/backtests/20260701_230342_20260702_entry_ev_external_hybrid_2025_0912_executable_admission_s1/`
- Support:
  - `data/reports/backtests/20260701_230343_20260702_entry_ev_external_hybrid_2025_0912_executable_support_s1/`
- Trade enrichment:
  - `data/reports/backtests/20260701_230357_20260702_entry_ev_external_hybrid_2025_0912_executable_trade_enrichment_s1/`

## Prediction Effect

| month | base long share | executable long share | side switch | base q95 | executable q95 | long factor | short factor |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-09 | `0.4590` | `0.3332` | `0.2492` | `31.6282` | `12.4031` | `0.1329` | `0.1904` |
| 2025-10 | `0.3596` | `0.2680` | `0.1930` | `37.7288` | `10.5833` | `0.1395` | `0.1885` |
| 2025-11 | `0.3956` | `0.2931` | `0.2425` | `38.3342` | `12.2278` | `0.1389` | `0.1941` |
| 2025-12 | `0.3990` | `0.3024` | `0.2444` | `37.6205` | `9.1734` | `0.1359` | `0.1768` |

Reading:

- Score shrinkage itself works.
- Long share also drops, but this does not mean selection quality improves.
- Because the source score already contains selector-blocked side values, side-gap quantiles remain contaminated by blocked-side magnitude. This run is a post-selector preflight, not the clean final design.

## Stateful Replay

| candidate | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `-27.5640` | `-26.8440` | `3` | `26.8440` | `0.6667` |
| q95/floor5/rank90 | `-29.5080` | `-26.8440` | `4` | `26.8440` | `0.5000` |

Comparison to 00270:

| candidate | 00270 total | executable total | delta | 00270 trades | executable trades |
|---|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `-28.3940` | `-27.5640` | `+0.8300` | `6` | `3` |
| q95/floor5/rank90 | `+0.0820` | `-29.5080` | `-29.5900` | `10` | `4` |

The q99 total is nearly unchanged and still NoTrade-below. q95 loses the near-flat result.

## Support And Admission

Support:

| candidate | quantile all | quantile hold | candidate rows | long rows | short rows |
|---|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `42` | `14` | `4` | `3` | `1` |
| q95/floor5/rank90 | `150` | `42` | `8` | `3` | `5` |

Admission:

| candidate | eligible | blockers | total pnl | worst month | trades |
|---|---|---|---:|---:|---:|
| q99/floor5/rank90 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` | `-27.5640` | `-26.8440` | `3` |
| q95/floor5/rank90 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` | `-29.5080` | `-26.8440` | `4` |

Selected policy remains:

```text
no_trade
```

## Trade Enrichment

| candidate | trades | total pnl | win rate | direction error | exit regret sum | EV overestimate mean | exit capture ratio mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `3` | `-27.5640` | `0.0000` | `0.3333` | `141.6740` | `15.3470` | `0.0000` |
| q95/floor5/rank90 | `4` | `-29.5080` | `0.0000` | `0.5000` | `163.0080` | `13.5626` | `0.0000` |

Reading:

- EV overestimate mean is smaller than 00271, so calibration direction is sensible.
- But all remaining stateful trades lose. Direct score replacement changed which trades enter, not just their calibration.
- The one-position path still matters; row-level EV shrinkage is insufficient.

## Decision

Accepted:

- external executable EV preflight evidence
- prior capture factor can shrink score scale on this fold

Rejected:

- post-selector executable EV direct score replacement
- using this q99/q95 replay as a policy candidate
- interpreting row-level score shrinkage as enough for stateful admission

Standard policy remains NoTrade.

## Next

1. Move capture factor earlier: apply it to base calibrated long/short EV before exit-regret selector and before side-gap quantile computation.
2. Re-run exit-regret selector on capture-adjusted base scores, instead of multiplying post-selector blocked scores.
3. Keep direct hard thresholding off; use NoTrade-first admission and role/month support gates.
4. Treat the post-selector executable run as a negative control.

## Verification

- executable EV policy input generation: OK
- q99/q95 stateful replay: OK
- support diagnostics: OK
- admission selector: OK
- executable trade enrichment: OK
