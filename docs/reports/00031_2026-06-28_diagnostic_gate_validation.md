# Diagnostic Gate Validation

日時: 2026-06-28 12:48 JST
更新日時: 2026-06-28 12:48 JST

## Summary

- Experiment ID: `diagnostic_gate_validation`
- Status: completed
- Main result: high-turnover validation 4foldを新diagnostic列入りで再生成した。2025-07 post-hoc smokeで使った厳しいgateはvalidation候補を全滅させるため、hard gateとして採用しない。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Data

- Model: `experiments/20260628_013141_full_fixed_horizon_blind_2025_06_barrier_prob_p1_l1p2/`
- Predictions: `predictions_valid.parquet`
- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Evaluation multiplier: profit `1.0`, loss `1.20`
- Cost-aware case: spread `0.1`, slippage `0.05`, delay `0`
- Base sweeps: `data/reports/backtests/20260628_034152_model_sweep_*/`, `data/reports/backtests/20260628_034327_model_sweep_*/`
- Cost sweeps: `data/reports/backtests/20260628_034241_model_sweep_*/`, `data/reports/backtests/20260628_034413_model_sweep_*/`
- Baseline candidate selection: `data/reports/backtests/20260628_034513_model_candidate_selection/`
- Threshold comparison: `data/reports/backtests/20260628_124813_diagnostic_gate_threshold_comparison.csv`

## Fixed Gate Context

前回のhigh-turnover基準は維持した。

- `min-trades-per-fold=10`
- `max-forced-exit-rate=0.05`
- `max-drawdown=100`
- `min-base-adjusted-pnl-per-fold=0`
- `min-cost-adjusted-pnl-per-fold=0`
- `max-side-loss-per-fold=100`
- `max-direction-session-loss-per-fold=60`
- `max-short-trade-share=0.65`
- `max-smoothed-actual-profit-barrier-miss-rate=0.55`

今回だけで追加検証したdiagnostic gate:

- `max-direction-error-rate`
- `max-predicted-side-error-rate`
- `max-no-edge-rate`
- `max-exit-regret-mean`
- `max-ev-overestimate-vs-realized-mean`

## Results

| gate | direction error | predicted side error | no edge | exit regret mean | EV overestimate | eligible |
|---|---:|---:|---:|---:|---:|---:|
| no diagnostic gate | `1.00` | `1.00` | `1.00` | inf | inf | 5 |
| lenient | `0.45` | `0.55` | `0.10` | `25.0` | `16.0` | 5 |
| balanced | `0.40` | `0.54` | `0.06` | `23.0` | `15.5` | 5 |
| focused | `0.37` | `0.51` | `0.05` | `22.5` | `14.5` | 2 |
| strict | `0.37` | `0.51` | `0.05` | `22.0` | `14.1` | 1 |
| 2025-07 smoke-like | `0.50` | `0.60` | `0.10` | `15.0` | `10.0` | 0 |

Baseline top candidate:

| side block | short offset | side margin | min entry rank | max wait regret | barrier | base min pnl | cost min pnl | min trades | direction error | predicted side error | exit regret mean | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 8 | 1 | 0.5 | 4 | 0.0 | `34.5186` | `20.6606` | 56 | `0.343750` | `0.500000` | `22.200057` | `14.415885` |

Strict gateで残る1候補:

| side block | short offset | side margin | min entry rank | max wait regret | barrier | base min pnl | cost min pnl | min trades | smoothed miss | direction error | predicted side error | exit regret mean | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `short:session_regime=asia` | 8 | 1 | 0.0 | 4 | 0.0 | `27.6424` | `12.5964` | 52 | `0.535211` | `0.362319` | `0.507246` | `21.750273` | `14.021809` |

## Interpretation

2025-07候補Aをpost-hocで落とせた `exit regret mean <= 15` と `EV overestimate <= 10` は、validation 4foldでは候補を全滅させる。これは未知月の失敗を見た後の閾値として強すぎるため、採用しない。

`balanced` までは候補数が5のままなので、diagnostic gateとしては候補集合を壊していない。ただし選別力もほぼない。

`focused` / `strict` は候補を2件/1件まで絞れるが、台地というより `short_offset=8`, `side_margin=1`, `max_wait_regret=4`, `profit_barrier_threshold=0.0` の狭い領域に寄る。strict候補はcost min pnlが `12.5964` まで下がる一方、smoothed missは `0.535211` と上限 `0.55` に近い。

現段階の判断:

- trade-analysis diagnosticsは今後のsweepに必ず出す。
- 2025-07 smoke-likeの厳しい閾値はhard gateにしない。
- `balanced` 程度は安全診断として記録できるが、候補選定の主役にはしない。
- `focused` / `strict` は、次のblind候補を固定するには台地が弱い。使うならtie-breakまたは追加validationでの安定確認が必要。
- profit barrier threshold `0.0` が残り続ける点は、barrier probability targetの選別力が弱い警告として扱う。

## Report Numbering Check

既存 `docs/reports/*.md` 30本について、本文冒頭の `日時` を抽出し、ファイル名の通し番号順と一致することを確認した。

- count: `30`
- ordered by internal datetime: `true`
- 基準にしたのはファイルシステムの更新時刻ではなく、各ファイル内の `日時`。

## Next Actions

1. 次のblindを見る前に、cost-awareを主目的にした候補選定基準を再固定する。
2. diagnostic gateは、validation候補を全滅させない範囲でtie-breakとして使う。
3. `profit_barrier_threshold=0.0` 依存を減らすため、barrier probability targetとexit timing targetを見直す。
4. 追加validationまたはwalk-forward OOFで、`exit_regret_mean` と `EV overestimate` の閾値が月をまたいで安定するかを確認する。
