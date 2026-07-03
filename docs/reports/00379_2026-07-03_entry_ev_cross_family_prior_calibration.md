# Entry EV Cross-Family Prior Calibration

日時: 2026-07-03 22:04 JST
更新日時: 2026-07-03 22:04 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00378で見えたearly-month prior不足に対し、replacement calibration診断へ `--prior-scope all_families_prior_months` と `--require-supported-candidates` を追加した。
- same-family priorでは `hgb2024_0306 2024-03` のprior rowsは0、supported candidateも0。
- all-family priorでは `hgb2024_0306 2024-03` にprior rows 276、supported candidates 1211が作れる。
- ただしall-family priorをそのまま使うとscore選択が不安定。全体summaryでは `side_score` が一番ましだが mean month PnL `-5.5427`、`prior_actual_mean` は `-13.1994`、raw/bias系はさらに悪化。
- `hgb2024_0306 2024-03` のworst lossだけを見ると、`side_score` は月PnLを `-17.6936 -> +10.5674` にできる一方、raw/bias/conservative系は同じ悪い720m candidateを選び `-43.5812` へ悪化する。
- 判断: cross-family priorは候補support不足を解くが、calibrationとしては安全ではない。標準policyはNoTrade。

## Artifacts

Same-family baseline:

- `data/reports/backtests/20260703_130129_20260703_entry_ev_00379_same_family_supported_replacement_calibration/`

All-family prior:

- `data/reports/backtests/20260703_130312_20260703_entry_ev_00379_all_family_supported_replacement_calibration/`

Code:

- `scripts/experiments/entry_ev_support_sufficient_replacement_calibration_diagnostics.py`

## Method

Added options:

```text
--prior-scope same_family
--prior-scope all_families_prior_months
--require-supported-candidates
```

`all_families_prior_months` pools candidate rows from all configured families where:

```text
prior month < target month
candidate_stage != non_candidate
```

Selection was forced to use only candidates whose calibration context meets `--min-prior-count`.

Run conditions:

```text
config: 00378_074738_long_tminus5_holdext_surface_config.json
targets:
  hgb2024_0306_external:2024-03:both
  fresh2024_validation:2024-03:both
  fresh2024_validation:2024-11:both
  refit2025_validation:2025-03:both
  hybrid2025_0912_external:2025-11:both
min_prior_count: 20
context:
  side,candidate_pred_fixed_best_horizon_minutes,combined_regime,session_regime
  side,candidate_pred_fixed_best_horizon_minutes,session_regime
  side,candidate_pred_fixed_best_horizon_minutes
  side
  all
```

This is a diagnostic. It does not change the selector surface policy.

## Target Support

| target | same prior rows | same supported | all prior rows | all supported |
|---|---:|---:|---:|---:|
| `hgb2024_0306 2024-03` | 0 | 0 | 276 | 1211 |
| `fresh2024 2024-03` | 0 | 0 | 276 | 20 |
| `fresh2024 2024-11` | 121 | 27 | 2263 | 27 |
| `refit2025 2025-03` | 664 | 1710 | 2963 | 1710 |
| `hybrid2025_0912 2025-11` | 231 | 46 | 6564 | 46 |

All-family prior solves the support-count problem for early targets, but it also brings cross-family scale/regime mismatch.

## Score Summary

All-family prior:

| score | choices | mean month PnL | best | worst | positive choices |
|---|---:|---:|---:|---:|---:|
| `side_score` | 17 | `-5.5427` | `+43.3400` | `-39.9600` | 16 |
| `prior_actual_mean` | 17 | `-13.1994` | `+25.9400` | `-21.0296` | 2 |
| `bias_corrected` | 17 | `-28.5130` | `+25.9400` | `-63.7412` | 7 |
| `raw_pred_fixed` | 17 | `-35.3644` | `+43.3400` | `-63.7412` | 6 |

This does not justify direct policy adoption.

## HGB 2024-03 Detail

For `hgb2024_0306 2024-03`, the worst loss was `-20.1840`.

| score | candidate side | horizon | candidate actual | month after | prior context | prior count |
|---|---|---:|---:|---:|---|---:|
| `side_score` | short | 240 | `+8.0770` | `+10.5674` | `side,horizon` | 76 |
| `prior_actual_mean` | long | 60 | `-3.3600` | `-0.8696` | `side,horizon,regime,session` | 21 |
| `raw_pred_fixed` | short | 720 | `-46.0716` | `-43.5812` | `side` | 100 |
| `bias_corrected` | short | 720 | `-46.0716` | `-43.5812` | `side` | 100 |
| `conservative` | short | 720 | `-46.0716` | `-43.5812` | `side` | 100 |

Important reading:

- Cross-family support makes a good candidate available.
- Current calibrated scores do not reliably select it.
- `prior_actual_mean` prefers a context with positive historical mean but chooses a losing long 60m candidate.
- Raw/bias scores chase a high predicted 720m candidate that is a large loss.

## Decision

Accepted:

- `prior_scope` infrastructure
- support-required replacement calibration diagnostics
- cross-family prior as diagnostic support source

Rejected:

- direct all-family prior adoption
- using cross-family prior_actual_mean as a replacement selector without additional shrinkage/gating
- relaxing same-family support globally

Standard policy remains NoTrade.

## Next

1. Add target-level outcome categories to surface/replacement reports:
   - loss selected but supported candidate 0
   - supported candidate exists but replacement score chooses a loser
   - supported candidate exists and replacement succeeds
2. For early-month targets, try shrunk cross-family priors with strict safeguards:
   - require context to be coarse enough for support but not dominated by 720m overestimate
   - penalize 720m when cross-family prior actual mean is negative
   - separate risk selection from replacement score selection
3. Re-test only as diagnostics until the method improves more than one target without winner damage.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_replacement_calibration_diagnostics.py tests/test_entry_ev_support_sufficient_replacement_calibration_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_replacement_calibration_diagnostics`: OK
- 00379 same-family supported calibration run: OK
- 00379 all-family supported calibration run: OK
