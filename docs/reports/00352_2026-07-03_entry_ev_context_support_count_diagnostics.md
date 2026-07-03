# Entry EV Context Support Count Diagnostics

日時: 2026-07-03 12:29 JST
更新日時: 2026-07-03 12:29 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00351の次アクションとして、context confidenceに `prior_observed_month_count`, `prior_flagged_month_count`, `prior_decision_count`, `prior_market_candidate_count`, flagged unique countsを追加した。
- `--min-prior-months`, `--min-prior-flagged-months`, `--min-prior-decisions` を追加した。defaultは0なので既存挙動は変えない。
- exact contextでは、00351と同じくdefault confident contextは0。問題contextは `prior_flagged_count=4` でも `prior_observed_month_count=1` しかなく、独立月supportが薄い。
- `horizon,side` まで粗くするとsupportは増えるが、defaultでは harmful/residual/720m がselected winnersを巻き込み、support2でも harmful/residual はselected winner damageを出す。
- 一方、`horizon,side` + support2 の `positive_bias_and_tail_miss_ge_0p10` はscenario-weightedで `-39210.5520` をflagし、selected winner damage 0。これは次のpre-registered replay候補だが、まだdiagnosticであり標準policyではない。
- `horizon,side,combined_regime` + support2 では全ruleが発火0。regimeまで入れるとsupportが薄くなる。
- 結論: exact context hard gateは薄い。horizon/side coarse gateは一部有望signalがあるがwinner damageも大きい。次はhard gateではなく、support-aware shrunk risk featureまたはpre-registered stateful replayへ進む。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_contextual_risk_confidence_diagnostics.py`

Updated tests:

- `tests/test_entry_ev_contextual_risk_confidence_diagnostics.py`

Runs:

- exact context:
  - `data/reports/backtests/20260703_032630_20260703_entry_ev_00352_context_support_counts_exact/`
- `horizon,side` default:
  - `data/reports/backtests/20260703_032659_20260703_entry_ev_00352_context_support_counts_horizon_side/`
- `horizon,side` support2:
  - `data/reports/backtests/20260703_032827_20260703_entry_ev_00352_context_support_counts_horizon_side_support2/`
- `horizon,side,combined_regime` support2:
  - `data/reports/backtests/20260703_032935_20260703_entry_ev_00352_context_support_counts_horizon_side_regime_support2/`

Superseded run:

- `data/reports/backtests/20260703_032733_20260703_entry_ev_00352_context_support_counts_horizon_side_support2/`
- This was rerun to include the new prior support columns in selected cases.

## Method

Added prior support columns:

- `prior_observed_month_count`
- `prior_flagged_month_count`
- `prior_decision_count`
- `prior_market_candidate_count`
- `prior_flagged_decision_count`
- `prior_flagged_market_candidate_count`

New optional confidence requirements:

- `--min-prior-months`
- `--min-prior-flagged-months`
- `--min-prior-decisions`

Sensitivity settings:

- exact context: default thresholds
- `horizon,side`: default thresholds
- `horizon,side` support2: `min_prior_months=2`, `min_prior_flagged_months=2`, `min_prior_decisions=5`
- `horizon,side,combined_regime` support2: same support2 thresholds

## Results

Rule summary:

| scope | rule | confident contexts | flags | flagged PnL | flagged losses | flagged wins | selected flagged win PnL | reading |
|---|---|---:|---:|---:|---:|---:|---:|---|
| exact | all rules | `0` | `0` | `0.0000` | `0` | `0` | `0.0000` | no confident exact context |
| `horizon,side` | `harmful_prob_ge_0p50` | `1` | `144` | `-2452.0320` | `144` | `0` | `0.0000` | clean but narrow |
| `horizon,side` | `tail_prob_ge_0p30` | `3` | `108` | `+1282.2120` | `0` | `108` | `0.0000` | current winners only |
| `horizon,side` | `harmful_prob_ge_0p30` | `2` | `1114` | `-2849.8280` | `630` | `484` | `+2526.4800` | selected winner damage |
| `horizon,side` | `positive_bias_and_tail_miss_ge_0p10` | `4` | `1720` | `-32608.4480` | `1080` | `640` | `+3078.2400` | selected winner damage |
| `horizon,side` support2 | `positive_bias_and_tail_miss_ge_0p10` | `3` | `1008` | `-39210.5520` | `1008` | `0` | `0.0000` | clean diagnostic signal |
| `horizon,side` support2 | `harmful_prob_ge_0p30` | `2` | `1114` | `-2849.8280` | `630` | `484` | `+2526.4800` | still damages selected winner |
| `horizon,side` support2 | `residual_tail_miss_ge_0p10` | `1` | `870` | `+4934.5280` | `144` | `726` | `+2526.4800` | over-gates winners |
| `horizon,side,regime` support2 | all rules | `0` | `0` | `0.0000` | `0` | `0` | `0.0000` | support too thin |

Exact target context support:

| context | rule | month | current flagged | current PnL | prior months | prior flagged months | prior decisions | prior flagged | prior delta | reading |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `720m short / down_normal_vol / london` | `tail_prob_ge_0p30` | `2025-08` | `1` | `+12.9400` | `1` | `1` | `4` | `4` | `+178.0692` | support is one month only and flips to win |
| `720m short / up_normal_vol / asia` | `tail_prob_ge_0p30` | `2025-11` | `5` | `-330.4680` | `0` | `0` | `0` | `0` | `0.0000` | no chronological prior |

Selected winner example under `horizon,side` support2:

| rule | trade | actual PnL | prior months | prior flagged months | prior decisions | prior flagged | prior delta | prior loss precision | reading |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `harmful_prob_ge_0p30` | `hybrid2025_0912_external 2025-11 short 60m` | `+10.4400` | `2` | `2` | `38` | `10` | `+24.2592` | `0.9000` | supported prior still flags winner |
| `residual_tail_miss_ge_0p10` | same trade | `+10.4400` | `2` | `2` | `38` | `27` | `+70.7050` | `0.7778` | supported prior still flags winner |

## Decision

- Prior support count columns are accepted infrastructure.
- Support thresholds are accepted diagnostic controls.
- Exact-context gate remains rejected: thin support.
- `horizon,side,combined_regime` hard confidence is too sparse under support2.
- `horizon,side` hard confidence is too coarse for harmful/residual/tail/720m rules because selected winners are still damaged.
- `horizon,side` + support2 + `positive_bias_and_tail_miss_ge_0p10` is a pre-registered diagnostic candidate for stateful replay, not a standard policy.
- Standard policy remains NoTrade.

## Next

1. Add a stateful replay hook for support-aware contextual positive-bias risk, starting with `horizon,side` + support2 + `positive_bias_and_tail_miss_ge_0p10`.
2. Keep harmful/residual as feature/calibration targets, not hard gates, until selected-winner damage is controlled.
3. Build shrunk risk features that blend `horizon,side` support with regime/session evidence instead of requiring exact-context hard confidence.
4. Continue candidate generation and exit timing work for thin months; context risk alone does not solve standard blockers.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_contextual_risk_confidence_diagnostics.py tests/test_entry_ev_contextual_risk_confidence_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_contextual_risk_confidence_diagnostics`: OK
- exact context support count diagnostics: OK
- `horizon,side` default diagnostics: OK
- `horizon,side` support2 diagnostics: OK
- `horizon,side,combined_regime` support2 diagnostics: OK
