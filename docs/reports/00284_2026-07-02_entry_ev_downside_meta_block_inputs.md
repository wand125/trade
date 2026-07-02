# Entry EV Downside Meta Block Inputs

日時: 2026-07-02 11:38 JST
更新日時: 2026-07-02 11:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00283の次アクションとして、raw cd15 entry scoreを維持したまま、supervised shrinkage outputを補助featureにした downside meta side-block inputを実装した。
- `scripts/experiments/entry_ev_downside_meta_block_policy_inputs.py` を追加し、selected raw cd15 tradesの realized downside を対象月より前だけで学び、prediction rowのlong/short両側へ `pred_downside_meta_*_expected_downside` と `*_block_gte_*` 列を付与した。
- `scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py` に `--side-block-rules` を追加し、dynamic exit replayでもside-block列を使えるようにした。
- OOF selected-trade診断では、閾値 `3.0` だけ小さく positive (`block_delta_if_removed +0.4200`) だが2 tradesしか拾わない。閾値 `1.0` 以下は勝ちtradeを削り、OOF上で明確に悪化。
- Stateful replayでも同じ。`gte1` blockはbaseline `+118.6900` から `+15.4886` へ大幅悪化。`gte3` blockはbaselineと完全一致し、実取引に作用しなかった。
- 判断: downside meta prediction-row inputとside-block replay経路はaccepted infrastructure。単純な expected downside threshold block はreject。次はblockではなく、month/role floorを損失に入れるmeta selector、またはsoft risk marginへ進む。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_downside_meta_block_policy_inputs.py`
  - `scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py`
- Test:
  - `tests/test_entry_ev_downside_meta_block_policy_inputs.py`
  - `tests/test_entry_ev_quantile_exit_timing_sensitivity.py`
- Policy input runs:
  - `data/reports/backtests/20260702_023257_20260702_entry_ev_downside_meta_block_cal2024_s1/`
  - `data/reports/backtests/20260702_023320_20260702_entry_ev_downside_meta_block_fresh2024_s1/`
  - `data/reports/backtests/20260702_023344_20260702_entry_ev_downside_meta_block_refit2025_s1/`
  - `data/reports/backtests/20260702_023408_20260702_entry_ev_downside_meta_block_hgb2024_0306_s1/`
  - `data/reports/backtests/20260702_023424_20260702_entry_ev_downside_meta_block_hgb2025_08_s1/`
  - `data/reports/backtests/20260702_023439_20260702_entry_ev_downside_meta_block_hybrid2025_0912_s1/`
- Replay runs:
  - `data/reports/backtests/20260702_023738_20260702_entry_ev_downside_meta_raw_cd15_internal_hgb_baseline_s1/`
  - `data/reports/backtests/20260702_023808_20260702_entry_ev_downside_meta_raw_cd15_hybrid_baseline_s1/`
  - `data/reports/backtests/20260702_023546_20260702_entry_ev_downside_meta_block_gte1_internal_hgb_replay_s1/`
  - `data/reports/backtests/20260702_023618_20260702_entry_ev_downside_meta_block_gte1_hybrid_replay_s1/`
  - `data/reports/backtests/20260702_023639_20260702_entry_ev_downside_meta_block_gte3_internal_hgb_replay_s1/`
  - `data/reports/backtests/20260702_023714_20260702_entry_ev_downside_meta_block_gte3_hybrid_replay_s1/`

## Method

Training target:

```text
target_downside = max(0, 0 - adjusted_pnl)
```

Chronology:

```text
target month M:
  train = selected raw cd15 trades with month < M
  predict = all prediction rows in month M, both long and short sides
```

Main features:

```text
raw selected/opposite EV
raw side gap and entry rank
loss-first probability
predicted holding minutes
fixed-horizon PnL proxies
supervised shrinkage score and shrink/raw ratio
family, side, combined_regime, session_regime, decision hour
```

Replay settings:

```text
entry score = raw cd15 benchmark score
candidate = q95_sg95_rank90_floor5_side_regime_session_month
variant = loss_exit30_cd15
profit_multiplier = 1.0
loss_multiplier = 1.2
max_hold = 24h
```

## OOF Threshold Diagnostics

Selected-trade OOF summary:

| threshold | flagged trades | flagged pnl | kept pnl if removed | block delta | loss precision | loss recall |
|---:|---:|---:|---:|---:|---:|---:|
| `3.00` | `2` | `-0.4200` | `119.1100` | `+0.4200` | `0.5000` | `0.0082` |
| `5.00` | `0` | `0.0000` | `118.6900` | `0.0000` | `0.0000` | `0.0000` |
| `2.00` | `11` | `+26.6000` | `92.0900` | `-26.6000` | `0.1818` | `0.0164` |
| `1.00` | `54` | `+132.5816` | `-13.8916` | `-132.5816` | `0.4074` | `0.1803` |
| `0.50` | `143` | `+147.5246` | `-28.8346` | `-147.5246` | `0.4825` | `0.5656` |
| `0.25` | `175` | `+115.6302` | `3.0598` | `-115.6302` | `0.4686` | `0.6721` |

Reading:

- The model does not separate losing rows cleanly. It flags many winners at practical thresholds.
- The only positive threshold is `3.0`, but support is 2 trades and recall is `0.0082`; this is too sparse to trust.
- `1.0` and below are not conservative risk gates. They are mostly high-activity suppression and damage the raw cd15 edge.

## Prediction Block Rate

Average row-level block share:

| family | long gte0.25 | short gte0.25 | long gte1 | short gte1 | long gte3 | short gte3 |
|---|---:|---:|---:|---:|---:|---:|
| cal2024 | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| fresh2024 | `0.3458` | `0.4337` | `0.0105` | `0.0641` | `0.0000` | `0.0000` |
| refit2025 | `0.7504` | `0.6932` | `0.0633` | `0.0966` | `0.0000` | `0.0003` |
| hgb2024_0306 | `0.2972` | `0.3686` | `0.0028` | `0.0169` | `0.0000` | `0.0000` |
| hgb2025_08 | `0.7266` | `0.8098` | `0.0642` | `0.0741` | `0.0000` | `0.0000` |
| hybrid2025_0912 | `0.8250` | `0.8212` | `0.0816` | `0.2152` | `0.0000` | `0.0000` |

Reading:

- `0.25` is far too broad and would act like a broad regime suppressor.
- `1.0` has enough activity to change replay, but OOF already says it deletes too many winning trades.
- `3.0` is almost no-op at prediction row level.

## Stateful Replay

Combined internal/HGB + hybrid:

| side-block | total pnl | trades | month min | role min | positive roles | max DD | decision |
|---|---:|---:|---:|---:|---:|---:|---|
| none baseline | `+118.6900` | `266` | `-6.8324` | `+0.0074` | `6/6` | `30.8714` | NoTrade |
| gte1 | `+15.4886` | `231` | `-11.6880` | `-16.6136` | `3/6` | `30.3984` | reject |
| gte3 | `+118.6900` | `266` | `-6.8324` | `+0.0074` | `6/6` | `30.8714` | no-op |

Worst months:

| side-block | family | month | pnl | trades |
|---|---|---|---:|---:|
| baseline | refit2025 | 2025-09 | `-6.8324` | `8` |
| baseline | refit2025 | 2025-06 | `-6.5136` | `6` |
| baseline | refit2025 | 2025-02 | `-6.0104` | `11` |
| gte1 | refit2025 | 2025-10 | `-11.6880` | `5` |
| gte1 | refit2025 | 2025-02 | `-6.0104` | `11` |
| gte1 | refit2025 | 2025-06 | `-4.8960` | `3` |
| gte3 | refit2025 | 2025-09 | `-6.8324` | `8` |
| gte3 | refit2025 | 2025-06 | `-6.5136` | `6` |
| gte3 | refit2025 | 2025-02 | `-6.0104` | `11` |

Reading:

- `gte1` does reduce some losing trades, but it removes too many winning opportunities and changes the stateful path into a worse refit2025-10 tail.
- `gte3` is not a usable conservative guard because it is effectively identical to no-block.
- The expected-downside scalar is not calibrated enough for a hard threshold. It should not become a direct side-block rule.

## Decision

Accepted:

- chronological downside meta input generation
- long/short prediction-row side-block columns
- `entry_ev_quantile_exit_timing_sensitivity.py` side-block passthrough
- replay split for internal/HGB raw score and hybrid base-executable raw score

Rejected:

- simple `pred_downside_meta_*_expected_downside >= threshold` as a hard block
- broad thresholds `0.25`, `0.5`, `1.0`
- sparse threshold `3.0` as evidence of risk control

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark.

## Next

1. Keep raw cd15 score path as the main entry score.
2. Use downside meta output as a soft risk feature, not a hard threshold.
3. Train/select against stateful outcomes with role/month floor penalties, not only selected-trade OOF flagged PnL.
4. Add risk margin variants: lower entry score by calibrated downside risk instead of outright side-blocking.
5. Add a candidate-level meta selector whose objective penalizes negative month floor and role floor directly.
6. Align train/apply feature semantics for opposite-side shrinkage. Selected-trade rows do not currently have a true opposite-side supervised shrink score, so the next version should either generate both sides for the train rows or avoid opposite shrink features entirely.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_downside_meta_block_policy_inputs.py tests/test_entry_ev_downside_meta_block_policy_inputs.py scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py`: OK
- `uv run python -m unittest tests.test_entry_ev_downside_meta_block_policy_inputs tests.test_entry_ev_quantile_exit_timing_sensitivity`: OK
- downside meta policy input generation for 6 families: OK
- raw cd15 baseline replay with downside-enriched parquets: OK
- gte1/gte3 side-block replay: OK
