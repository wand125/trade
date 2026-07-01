# Entry EV External Hybrid Base Executable Selector

日時: 2026-07-02 08:10 JST
更新日時: 2026-07-02 08:10 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00272の反省を受け、capture factorをpost-selector scoreではなくselector前のbase calibrated scoreへ掛けた。
- そのbase executable scoreを使って、exit-regret riskとpre-block side-gap selectorを再生成した。
- post-selector補正よりは改善したが、NoTradeは超えない。
- q99/floor5/rank90は `-27.4800`, 2 trades。q95/floor5/rank90は `-12.1040`, 4 trades。
- q95は00272 post-selector executable `-29.5080` から改善したが、00270のnear-flat `+0.0820` には届かない。
- supportはq99 2 candidate rows、q95 13 candidate rows。admissionは両方NoTrade。
- 判断: capture factorをselector前へ入れる方針は00272より筋が良い。ただし単独score化では2025-12 short tailを止められない。次はcapture-adjusted scoreにside/regime tail riskまたはdirection-side robustness headを併用する。

## Artifacts

- Base executable inputs:
  - `data/reports/backtests/20260701_230913_20260702_entry_ev_external_hybrid_2025_0912_base_executable_inputs_s1/`
- Base executable exit-regret risk:
  - `data/reports/backtests/20260701_230926_20260702_entry_ev_external_hybrid_2025_0912_base_executable_exit_regret_risk_s1/`
- Base executable pre-block selector:
  - `data/reports/backtests/20260701_230940_20260702_entry_ev_external_hybrid_2025_0912_base_executable_preblock_selector_t0p4_s1/`
- Stateful replay:
  - `data/reports/backtests/20260701_230954_20260702_entry_ev_external_hybrid_2025_0912_base_executable_selector_replay_s1/`
- Admission:
  - `data/reports/backtests/20260701_231020_20260702_entry_ev_external_hybrid_2025_0912_base_executable_selector_admission_s1/`
- Support:
  - `data/reports/backtests/20260701_231021_20260702_entry_ev_external_hybrid_2025_0912_base_executable_selector_support_s1/`
- Trade enrichment:
  - `data/reports/backtests/20260701_231021_20260702_entry_ev_external_hybrid_2025_0912_base_executable_selector_trade_enrichment_s1/`

## Prediction Effect

Before selector, base executable score effect:

| month | base long share | executable long share | side switch | base q95 | executable q95 | long factor | short factor |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-09 | `0.5297` | `0.4055` | `0.3680` | `31.8511` | `12.4578` | `0.1329` | `0.1904` |
| 2025-10 | `0.4272` | `0.2997` | `0.2637` | `37.7722` | `10.7421` | `0.1395` | `0.1885` |
| 2025-11 | `0.4507` | `0.3212` | `0.2980` | `38.3435` | `12.4402` | `0.1389` | `0.1941` |
| 2025-12 | `0.4831` | `0.3789` | `0.3183` | `37.6429` | `10.4232` | `0.1359` | `0.1768` |

Exit-regret selector block rate stayed close to 00270:

| long block | short block | any side block | selected side changed |
|---:|---:|---:|---:|
| `0.2254` | `0.0982` | `0.2790` | `0.1234` |

## Replay

| candidate | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| q95/floor5/rank90 | `-12.1040` | `-26.7600` | `4` | `26.7600` | `0.7500` |
| q99/floor5/rank90 | `-27.4800` | `-26.7600` | `2` | `26.7600` | `0.5000` |

Comparison:

| branch | q99 total | q95 total | q99 trades | q95 trades |
|---|---:|---:|---:|---:|
| 00270 original selector | `-28.3940` | `+0.0820` | `6` | `10` |
| 00272 post-selector executable | `-27.5640` | `-29.5080` | `3` | `4` |
| 00273 base executable selector | `-27.4800` | `-12.1040` | `2` | `4` |

Reading:

- Moving capture factor before selector avoids the worst q95 degradation from 00272.
- It still removes too much exposure and keeps the 2025-12 loss.
- The q95 improvement vs 00272 is not enough for policy candidacy.

## Support And Admission

Support:

| candidate | quantile all | quantile hold | candidate rows | long rows | short rows |
|---|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `98` | `4` | `2` | `1` | `1` |
| q95/floor5/rank90 | `353` | `23` | `13` | `1` | `12` |

Admission:

| candidate | eligible | blockers | total pnl | worst month | trades |
|---|---|---|---:|---:|---:|
| q95/floor5/rank90 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` | `-12.1040` | `-26.7600` | `4` |
| q99/floor5/rank90 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` | `-27.4800` | `-26.7600` | `2` |

Selected policy:

```text
no_trade
```

## Trade Enrichment

| candidate | trades | total pnl | win rate | direction error | exit regret sum | EV overestimate mean | exit capture ratio mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| q95/floor5/rank90 | `4` | `-12.1040` | `0.2500` | `0.5000` | `203.6810` | `9.6221` | `0.0406` |
| q99/floor5/rank90 | `2` | `-27.4800` | `0.0000` | `0.5000` | `92.9000` | `20.3318` | `0.0000` |

Reading:

- EV overestimate mean is lower than 00271 and lower than q99/q95 original, so calibration still helps the score scale.
- The remaining selected trades have poor capture ratio and large exit regret.
- q95 keeps one positive 2025-10 cluster but loses on 2025-12.

## Decision

Accepted:

- selector-before capture placement is better than post-selector capture placement
- base executable selector as a negative/diagnostic branch

Rejected:

- standardizing q99/q95 base executable selector
- direct executable score replacement without side/regime tail control
- treating lower EV overestimate as sufficient policy evidence

Standard policy remains NoTrade.

## Next

1. Do not tune q95/q99 thresholds on this same fold.
2. Add a side/regime tail-risk head or direction-side robustness head on top of capture-adjusted base score.
3. Specifically diagnose the residual 2025-12 `short/down_high_vol/rollover` loss as a target feature, not as a static blacklist.
4. If applying prior guard again, regenerate it on capture-adjusted selector rows; do not reuse old branch conclusions blindly.

## Verification

- base executable input generation: OK
- exit-regret risk generation: OK
- pre-block selector input generation: OK
- q99/q95 stateful replay: OK
- support diagnostics: OK
- admission selector: OK
- trade enrichment: OK
