# Entry EV Near-Miss Horizon Viability

日時: 2026-07-02 20:53 JST
更新日時: 2026-07-02 20:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00320の次アクションとして、PnL-regression argmaxをやめ、horizon-specific binary viability / abstention-first decisionを実装した。
- `scripts/experiments/entry_ev_near_miss_horizon_viability.py` を追加し、60/240/720mごとに executable classifier、PnL regressor、tail-loss classifierをchronologicalに学習した。
- default runでは available candidates の60m executable AUCが `0.6635`、greedy selectedの240m executable AUCが `0.6167` と一部の識別力は出た。
- しかしtail-loss headが弱く、defaultのavailable candidates 60m tail-loss AUCは `0.3225`、greedy selected 720m tail-loss AUCは `0.3333`。
- threshold後の実PnLは全runで負。default bestはgreedy selected `-36.8370`、model-used必須では `-39.9600`、available candidatesでは `-354.5204`。
- 判断: horizon-specific viability diagnosticsはaccepted infrastructure。current direct horizon selector / near-miss support overlayはreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_near_miss_horizon_viability.py`
- New tests:
  - `tests/test_entry_ev_near_miss_horizon_viability.py`
- Runs:
  - default: `data/reports/backtests/20260702_114935_20260702_entry_ev_00321_near_miss_horizon_viability_00319_s1/`
  - available-only training: `data/reports/backtests/20260702_115024_20260702_entry_ev_00321_near_miss_horizon_viability_00319_s2_available_train/`
  - min train 3 months / 30 rows: `data/reports/backtests/20260702_115023_20260702_entry_ev_00321_near_miss_horizon_viability_00319_s3_m3r30/`

## Method

Input:

```text
near_miss_exit_target_rows.csv from 00319
horizons = 60, 240, 720 minutes
chronological split = train rows with month < target month
default min train = 2 months / 20 rows
default train universe = all near-miss rows
model = HistGradientBoosting classifier/regressor
```

Targets per horizon:

- `target_fixed_{horizon}m_executable`
- `side_fixed_{horizon}m_adjusted_pnl`
- `target_fixed_{horizon}m_tail_loss`

Decision:

```text
choose horizon only if:
  executable probability >= threshold
  predicted PnL >= EV threshold
  tail-loss probability <= threshold
  and, optionally, model_used is true for all three heads
otherwise abstain
```

This preserves the 00320 lesson: fallback rows and predicted PnL argmax are not enough. The selector must be allowed to choose no trade.

## Main Results

Default AUC summary:

| scope | horizon | executable AUC | tail-loss AUC | model-used share |
|---|---:|---:|---:|---:|
| available candidates | 60m | `0.6635` | `0.3225` | `0.7652` |
| available candidates | 240m | `0.4055` | `0.5592` | `0.7652` |
| available candidates | 720m | `0.5209` | `0.4359` | `0.7652` |
| greedy selected | 60m | `0.5667` | `0.5000` | `0.8182` |
| greedy selected | 240m | `0.6167` | `0.6667` | `0.8182` |
| greedy selected | 720m | `0.5000` | `0.3333` | `0.8182` |

Best threshold comparison:

| run | scope | require model-used | best threshold | chosen | model-used | actual PnL | executable rate |
|---|---|---:|---|---:|---:|---:|---:|
| default | greedy selected | no | prob `0.5`, EV `2`, tail `0.3` | `2` | `1` | `-36.8370` | `0.5000` |
| default | greedy selected | yes | prob `0.5`, EV `2`, tail `0.3` | `1` | `1` | `-39.9600` | `0.0000` |
| default | available candidates | yes | prob `0.8`, EV `-2`, tail `0.3` | `14` | `14` | `-354.5204` | `0.4286` |
| available train | greedy selected | no | prob `0.5`, EV `2`, tail `0.3` | `2` | `1` | `-36.8370` | `0.5000` |
| available train | available candidates | yes | prob `0.5`, EV `5`, tail `0.3` | `10` | `10` | `-349.8814` | `0.3000` |
| min 3m/30r | greedy selected | no | prob `0.5`, EV `2`, tail `0.3` | `2` | `1` | `-36.8370` | `0.5000` |
| min 3m/30r | available candidates | yes | prob `0.8`, EV `-2`, tail `0.3` | `14` | `14` | `-354.5204` | `0.4286` |

The greedy selected best threshold chooses two rows:

| row | target fixed-best | target horizon | chosen horizon | actual at choice | model used |
|---|---:|---:|---:|---:|---:|
| fresh2024 2024-08 long | `+3.1230` | `240` | `240` | `+3.1230` | `False` |
| hybrid2025 2025-11 short | `+0.8200` | `60` | `720` | `-39.9600` | `True` |

The only positive selected row is fallback. The learned selected row is the known bad hybrid 2025-11 short 720m path.

## Failure Pattern

The executable head is not the main blocker. The default available-candidate 60m executable AUC is usable as a diagnostic signal. The actual failure is the combination of:

- tail-loss probability is unstable and sometimes inverted;
- PnL regression still overestimates dangerous 720m paths;
- abstention gate suppresses many positive 720m fixed-best opportunities but keeps the hybrid 2025-11 short loss;
- near-miss rows are too small and path-dependent to serve as a standalone direct decision surface.

This confirms the concern from 00320: horizon selection must not be reduced to PnL argmax, but binary viability alone is still not enough.

## Decision

Accepted:

- horizon-specific executable / tail-loss / PnL head infrastructure
- prior-month-only chronological training for horizon viability
- abstention-first threshold summary and model-used filtering
- sensitivity run structure for training universe and minimum training support

Rejected:

- current direct horizon-specific viability selector as policy
- current side-balanced near-miss support overlay
- treating 60m executable AUC improvement as sufficient evidence
- using fallback positive rows as edge evidence

Standard policy remains NoTrade.

## Next

1. Keep horizon-specific viability outputs as features/diagnostics, not as a direct selector.
2. Train the same heads on a broader candidate universe instead of only near-miss support rows, then evaluate near-miss rows as an out-of-sample slice.
3. Improve tail-loss and PnL calibration before reopening 720m exits; especially block the hybrid 2025-11 short failure shape.
4. Only connect side-balanced support overlay to stateful replay after model-used, tail-loss, and PnL calibration gates pass.
5. Continue using 00317 repair target as a support/side readiness check; support count improvement alone is not progress.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_near_miss_horizon_viability.py tests/test_entry_ev_near_miss_horizon_viability.py`: OK
- `uv run python -m unittest tests.test_entry_ev_near_miss_horizon_viability`: OK
- `uv run python -m unittest tests.test_entry_ev_near_miss_horizon_viability tests.test_entry_ev_near_miss_exit_head tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00321 near-miss horizon viability runs: OK
