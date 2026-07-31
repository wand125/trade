# Entry EV Loss First Global Expanding Quantile

日時: 2026-07-02 09:54 JST
更新日時: 2026-07-02 09:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00278の次アクションとして、raw `loss_first_exit_threshold=0.30` を絶対確率のまま使わず、過去分布上のquantileへ置き換える診断を実施した。
- `scripts/experiments/entry_ev_loss_first_quantile_inputs.py` を追加し、各評価月より前の全prediction rowだけをfit分布に使う `global expanding` empirical-CDF列を生成した。
- `entry_ev_quantile_exit_timing_sensitivity.py` は `--long-loss-first-column` / `--short-loss-first-column` を受け取れるようにした。
- fit不足月をNaNにするとrequired prediction column欠損でentry自体が消えるため、fit不足時はquantile `0.0` で埋め、dynamic exitだけを無効化する設計にした。
- 内部chronologyでは `lfq60_cd15` が total `+117.1112` まで伸びたが、role min `-4.2906`, month min `-28.9404` でraw `loss_exit30_cd15` の month min `-6.8324` より悪い。
- 外部HGB/hybrid固定適用も、combinedでは raw `loss_exit30_cd15` が total `+118.6900`, positive roles `6/6`, month min `-6.8324` で最も安定。`lfq60_cd15` は total `+135.3536` だが positive roles `4/6`, month min `-28.9404`。
- 判断: chronological quantile input infrastructureはaccepted。ただし単純なglobal expanding loss-first quantile thresholdは現policy候補にしない。q95 + raw `loss_exit30_cd15` を固定診断候補として維持する。

## Artifacts

- Added:
  - `scripts/experiments/entry_ev_loss_first_quantile_inputs.py`
  - `tests/test_entry_ev_loss_first_quantile_inputs.py`
- Updated:
  - `scripts/experiments/entry_ev_quantile_policy_backtest.py`
  - `scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py`
  - `tests/test_entry_ev_quantile_policy_backtest.py`
- Quantile inputs:
  - `data/reports/backtests/20260702_004620_20260702_entry_ev_loss_first_global_expanding_quantile_s2/`
- Replays:
  - `data/reports/backtests/20260702_004652_20260702_entry_ev_loss_first_quantile_cd15_internal_s2/`
  - `data/reports/backtests/20260702_005309_20260702_entry_ev_external_hgb_loss_first_quantile_cd15_s2/`
  - `data/reports/backtests/20260702_005332_20260702_entry_ev_external_hybrid_loss_first_quantile_cd15_s2/`

## Method

Quantile columns:

```text
pred_long_loss_first_global_expanding_quantile
pred_short_loss_first_global_expanding_quantile
```

For each target month:

```text
fit distribution = all prediction rows with dataset_month < target_month
apply rows = rows in target month
quantile = empirical CDF score of raw loss-first probability within fit distribution
```

Important:

- Same-month rows and future rows are not used.
- The pool is global across supplied families, not family-local.
- When `fit_rows < 1000`, output quantile is filled with `0.0`; this preserves entry eligibility while preventing dynamic exit from firing without a calibration distribution.

Replay variants:

| variant | dynamic exit column | threshold | cooldown |
|---|---|---:|---:|
| `lfq30_cd15` | global expanding quantile | `0.30` | `15m` |
| `lfq50_cd15` | global expanding quantile | `0.50` | `15m` |
| `lfq60_cd15` | global expanding quantile | `0.60` | `15m` |
| `lfq70_cd15` | global expanding quantile | `0.70` | `15m` |
| `lfq80_cd15` | global expanding quantile | `0.80` | `15m` |
| `lfq90_cd15` | global expanding quantile | `0.90` | `15m` |

Baseline for comparison is 00278 raw `loss_exit30_cd15`.

## Internal Results

Internal chronology:

| variant | total pnl | role min | month min | trades | max DD |
|---|---:|---:|---:|---:|---:|
| `lfq60_cd15` | `+117.1112` | `-4.2906` | `-28.9404` | `132` | `45.6476` |
| `lfq80_cd15` | `+102.1216` | `-2.0826` | `-49.2840` | `128` | `49.5890` |
| `lfq70_cd15` | `+99.0370` | `-2.7306` | `-31.6284` | `129` | `46.0886` |
| `lfq50_cd15` | `+80.4762` | `+0.1494` | `-28.9404` | `134` | `52.3076` |
| `lfq90_cd15` | `+74.0326` | `-1.6986` | `-73.4770` | `123` | `105.1570` |
| `lfq30_cd15` | `+68.1008` | `+0.1494` | `-19.3174` | `140` | `32.9940` |
| raw `loss_exit30_cd15` | `+83.5766` | `+8.3344` | `-6.8324` | `164` | `30.8714` |

Reading:

- quantile版はtotalを伸ばす場合があるが、tailが大きく悪化する。
- `lfq30/50` は全role positiveを維持するが、role minが `+0.1494` まで痩せ、month floorはrawより悪い。
- `lfq60` はtotal最大だが、cal2024 roleとHGB externalで崩れる兆候がある。
- raw `0.30` は単純なglobal quantileでは置き換えられない。

## External Fixed Check

HGB external:

| variant | total pnl | role min | month min | trades |
|---|---:|---:|---:|---:|
| `lfq50_cd15` | `+26.3734` | `+12.7868` | `-2.8560` | `88` |
| `lfq30_cd15` | `+13.5642` | `+6.0202` | `-1.8812` | `91` |
| `lfq60_cd15` | `+13.5244` | `-6.3056` | `-15.2002` | `85` |
| raw `loss_exit30_cd15` | `+28.4894` | `+0.0074` | `+0.0074` | `96` |

Hybrid external:

| variant | total pnl | role min | month min | trades |
|---|---:|---:|---:|---:|
| `lfq30_cd15` | `+6.0900` | `+6.0900` | `-0.7200` | `5` |
| `lfq50_cd15` | `+5.2220` | `+5.2220` | `-5.8440` | `5` |
| `lfq60_cd15` | `+4.7180` | `+4.7180` | `-5.7480` | `5` |
| raw `loss_exit30_cd15` | `+6.6240` | `+6.6240` | `-4.1460` | `6` |

Reading:

- HGBではraw `cd15` が唯一month min非負。
- Hybridでは `lfq30` がmonth minを改善するが、HGB/internalの悪化を補えない。

## Combined View

Internal + external HGB + external hybrid:

| variant | total pnl | role min | positive roles | month min | trades | max DD |
|---|---:|---:|---:|---:|---:|---:|
| raw `loss_exit30_cd15` | `+118.6900` | `+0.0074` | `6/6` | `-6.8324` | `266` | `30.8714` |
| `lfq30_cd15` | `+87.7550` | `+0.1494` | `6/6` | `-19.3174` | `236` | `32.9940` |
| `lfq50_cd15` | `+112.0716` | `+0.1494` | `6/6` | `-28.9404` | `227` | `52.3076` |
| `lfq60_cd15` | `+135.3536` | `-6.3056` | `4/6` | `-28.9404` | `222` | `45.6476` |

Reading:

- `lfq60` はtotalだけなら最大だが、role/month floorを壊しているためreject。
- `lfq30/50` はall-role positiveだが、raw `cd15` よりmonth floorが大きく悪い。
- global expanding quantileは、raw probability scale driftへの対策としては不十分。特にrefit2025のshort loss-first分布が高quantile側へ寄り、exit timingが局所的に過剰/過少になる。

## Decision

Accepted:

- chronological loss-first quantile input generation
- loss-first column override in entry-EV quantile replay
- fit不足時に `0.0` fillでentryを保ち、dynamic exitだけを無効化する扱い

Rejected:

- q95 + `lfq30_cd15`
- q95 + `lfq50_cd15`
- q95 + `lfq60_cd15`
- replacing raw `loss_exit30_cd15` with simple global expanding quantile threshold

Standard policy remains NoTrade.

Current fixed diagnostic candidate remains q95 + raw `loss_exit30_cd15`.

## Next

1. Do not keep sweeping global loss-first quantile thresholds on the same windows.
2. If revisiting calibration, use side/family/regime-conditioned calibration or supervised exit-capture calibration, not a single global CDF.
3. Return to residual loss decomposition for raw `loss_exit30_cd15`:
   - refit churn losses: 2025-02/03/06/08/09
   - hybrid sparse losses: 2025-11/12
   - fresh sparse losses: 2024-03/11
4. Keep raw `loss_exit30_cd15` frozen while diagnosing remaining negative months.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_loss_first_quantile_inputs.py tests/test_entry_ev_loss_first_quantile_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_loss_first_quantile_inputs`: OK
- internal quantile replay: OK
- external HGB quantile replay: OK
- external hybrid quantile replay: OK
