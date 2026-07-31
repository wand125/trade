# Entry EV Broad Horizon Viability

日時: 2026-07-02 21:21 JST
更新日時: 2026-07-02 21:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00321の反省として、near-missだけでhorizon viability headを学習するとサンプルが薄く、tail-loss / PnL calibrationが不安定だった。
- `scripts/experiments/entry_ev_broad_horizon_viability.py` を追加し、広いprediction-row candidate universeで60/240/720mのexecutable / PnL / tail-loss headを学習し、評価は00319のnear-miss rowsに限定した。
- `scripts/experiments/entry_ev_horizon_choice_nonoverlap_audit.py` を追加し、raw threshold choicesを一玉制約に近いnon-overlap greedy監査へ通した。
- q90 broad trainingは00321より改善した。s1では available candidates のmodel-used raw bestが `+23.5350`、非重複後 `+14.8160`。greedy selectedはmodel-used raw `+16.8700`、非重複後 `+13.7800`。
- q90 + one-failed trainingが最も強い診断結果だった。available candidates はraw `+71.3850`、非重複後 `+18.4790`。greedy selected はraw `+34.3230`、非重複後 `+20.5430`。
- ただしavailable側のraw利益は近接entry clusterに強く依存し、非重複後は3本程度へ縮む。これはまだstateful policy evidenceではない。
- score>=5 broad trainingは大きく失敗した。available candidates はraw `-40.6836`、非重複後 `-12.8676`。高score universeだけでは720m tail overfitを再導入する。
- 判断: broad candidate universe horizon viabilityとnon-overlap auditはaccepted infrastructure。q90 + one-failed trainingはdiagnostic candidateとして残すが、raw threshold PnLを標準policy evidenceとしては扱わない。標準policyはNoTrade。

## Artifacts

- New scripts:
  - `scripts/experiments/entry_ev_broad_horizon_viability.py`
  - `scripts/experiments/entry_ev_horizon_choice_nonoverlap_audit.py`
- New tests:
  - `tests/test_entry_ev_broad_horizon_viability.py`
  - `tests/test_entry_ev_horizon_choice_nonoverlap_audit.py`
- Runs:
  - s1 q90 broad training: `data/reports/backtests/20260702_120911_20260702_entry_ev_00322_broad_horizon_viability_00321_s1/`
  - s2 q90 + one-failed training: `data/reports/backtests/20260702_121505_20260702_entry_ev_00322_broad_horizon_viability_00321_s2_include_onefail/`
  - s3 score>=5 broad training: `data/reports/backtests/20260702_121524_20260702_entry_ev_00322_broad_horizon_viability_00321_s3_score5/`

Each run writes:

- `broad_horizon_viability_predictions.csv`
- `broad_horizon_viability_metric_summary.csv`
- `broad_horizon_viability_threshold_summary.csv`
- `broad_horizon_viability_threshold_choices.csv`
- `broad_horizon_viability_nonoverlap_summary.csv`
- `broad_horizon_viability_nonoverlap_choices.csv`

## Method

Input:

```text
eval rows = 00319 near_miss_exit_target_rows.csv
training rows = side-expanded prediction parquet rows from 00314 fixed60 uncertainty margin inputs
horizons = 60, 240, 720 minutes
chronological split = train rows with month < target month
model = HistGradientBoosting classifier/regressor
max_iter = 80
loss/evaluation unit = adjusted PnL columns inherited from the current 1.0 / 1.20 evaluation regime
```

Broad training universe:

| run | filter | train rows |
|---|---|---:|
| s1 | `holding_ok`, `score >= 0`, `score_pct >= 0.90`, `side_margin_pct >= 0.90`, `entry_rank_pct >= 0.80` | `4303` |
| s2 | s1 + `one_failed_strict_stage` rows included | `9697` |
| s3 | `holding_ok`, `score >= 5` | `90447` |

Decision:

```text
choose horizon only if:
  executable probability >= threshold
  predicted PnL >= EV threshold
  tail-loss probability <= threshold
  and optionally all heads are model_used
otherwise abstain
```

Non-overlap audit:

```text
sort chosen rows by predicted choice score
keep the row only if its [entry, exit] interval does not overlap an already kept row
summarize raw choices and non-overlap choices side by side
```

This is not a full stateful replay. It is a guardrail to avoid over-reading adjacent candidate clusters.

## Main Results

Metric highlights:

| run | scope | metric | value |
|---|---|---|---:|
| s1 q90 | available 240m | tail-loss AUC | `0.6800` |
| s1 q90 | available 240m | executable AUC | `0.5747` |
| s1 q90 | greedy 240m | executable AUC | `0.5333` |
| s2 q90 + one-failed | available 240m | tail-loss AUC | `0.7145` |
| s2 q90 + one-failed | available 720m | executable AUC | `0.5805` |
| s2 q90 + one-failed | greedy 240m | executable AUC | `0.6333` |
| s3 score>=5 | available 240m | tail-loss AUC | `0.7441` |
| s3 score>=5 | greedy 720m | tail-loss AUC | `0.0000` |

Threshold and non-overlap comparison:

| run | scope | threshold | raw chosen | raw PnL | non-overlap chosen | non-overlap PnL |
|---|---|---|---:|---:|---:|---:|
| s1 q90 | available | prob `0.6`, EV `2`, tail `0.3`, model-used yes | `7` | `+23.5350` | `3` | `+14.8160` |
| s1 q90 | greedy | prob `0.5/0.6`, EV `5`, tail `0.5/0.7`, model-used yes | `2` | `+16.8700` | `1` | `+13.7800` |
| s2 q90 + one-failed | available | prob `0.6`, EV `2`, tail `0.3`, model-used yes | `8` | `+71.3850` | `3` | `+18.4790` |
| s2 q90 + one-failed | greedy | prob `0.6`, EV `-2`, tail `0.3/0.5/0.7`, model-used yes | `5` | `+34.3230` | `4` | `+20.5430` |
| s3 score>=5 | available | prob `0.8`, EV `-2/0/2`, tail `0.3/0.5/0.7`, model-used yes | `3` | `-40.6836` | `1` | `-12.8676` |
| s3 score>=5 | greedy | prob `0.5`, EV `2`, tail `0.3`, model-used yes | `2` | `-4.4600` | `2` | `-4.4600` |

The s2 available-candidate raw result is the strongest row-level signal, but it is also the most misleading if read as a policy result. Most of the `+71.3850` raw PnL comes from overlapping clusters around `refit2025 2025-08` and `hybrid2025_0912 2025-10`. Once non-overlap is enforced, the same threshold retains only 3 rows and `+18.4790`.

## Failure Pattern

Broad training improves the 00321 issue where the near-miss-only head was too sparse. The improvement is visible in:

- s2 available 240m tail-loss AUC `0.7145`;
- s2 greedy 240m executable AUC `0.6333`;
- model-used thresholds no longer depending only on fallback positive rows;
- positive non-overlap PnL in s1/s2.

The remaining weaknesses are still policy-level blockers:

- raw threshold choices can select multiple overlapping entries inside the same price move;
- s2 greedy best uses EV threshold `-2`, so the selector is not yet consistently positive-EV at decision time;
- available-candidate raw PnL is not a one-position stateful replay;
- s3 shows that a much wider score>=5 universe can learn a plausible tail-loss head but still choose bad 720m paths;
- 720m decisions remain fragile and can reopen the same overfit pattern from 00320/00321.

## Decision

Accepted:

- broad candidate universe training for horizon-specific viability heads
- side-expanded prediction-row training data generation
- prior-month-only chronological train/eval split for broad rows
- deterministic max train rows cap
- non-overlap audit for horizon threshold choices

Diagnostic candidate:

- q90 + one-failed broad training as a feature source for support-repair rows
- s2 horizon viability predictions as inputs to stateful support repair replay

Rejected:

- raw threshold PnL as policy evidence
- score>=5 broad training universe as current standard
- available-candidate threshold choices without non-overlap/stateful replay
- reopening 720m exits from row-level threshold evidence alone

Standard policy remains NoTrade.

## Next

1. Feed s2 q90 + one-failed horizon viability predictions into a stateful support-repair replay.
2. Add non-overlap-aware threshold selection or stateful replay before comparing PnL candidates.
3. Keep EV threshold sensitivity explicit; do not treat negative-EV threshold wins as standard evidence.
4. Diagnose the s3 bad 720m selections and add 720m tail blocking before any broad score>=5 retrial.
5. Continue using 00317 repair target: extra trades only count as progress if they improve support/side readiness without reopening tail losses.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_horizon_viability.py tests/test_entry_ev_broad_horizon_viability.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_horizon_viability`: OK
- `uv run python -m py_compile scripts/experiments/entry_ev_horizon_choice_nonoverlap_audit.py tests/test_entry_ev_horizon_choice_nonoverlap_audit.py`: OK
- `uv run python -m unittest tests.test_entry_ev_horizon_choice_nonoverlap_audit`: OK
- 00322 broad horizon viability runs: OK
- 00322 non-overlap audit runs: OK
