# Entry EV External Hybrid Side Regime Tail Risk

日時: 2026-07-02 08:25 JST
更新日時: 2026-07-02 08:25 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00273の次アクションとして、capture-adjusted base selector scoreに chronological side/regime tail-risk headを重ねた。
- `scripts/experiments/entry_ev_side_regime_tail_policy_inputs.py` を追加し、common-entry targetを対象月より前の月だけで `direction + combined_regime` または `direction + combined_regime + session_regime` に集計し、prediction rowへtail riskと補正scoreを付与した。
- coarse `direction_regime` では、`direction_side_inversion_target` s0.25、`exit_capture_failure_target` s0.1/s0.25が同じstateful経路になり、q99/floor5/rank90は total `+3.1260`, worst month `-0.7200`, 3 tradesまで改善した。
- ただしq99は全tradeがlong、max side share `1.0000`、candidate rowsも4 rowsだけ。admissionは `month_pnl_below_floor;role_trades_low;month_trades_low;side_share_high` でNoTrade。
- q95は total `-7.2060`, worst month `-4.5420`, 5 tradesでNoTrade。
- `direction_regime` s0.1と細かい `side_context` s0.25は q99 `-27.5640`, q95 `-29.5080` へ戻り、00272相当の悪い経路になった。
- 判断: coarse side/regime tail riskは有望なdiagnostic head。ただし同一外部fold上の薄いsupportと片側集中なので標準policyにはしない。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_side_regime_tail_policy_inputs.py`
- Added test:
  - `tests/test_entry_ev_side_regime_tail_policy_inputs.py`
- Direction-regime inputs:
  - `data/reports/backtests/20260701_232211_20260702_entry_ev_external_hybrid_side_regime_dirinv_tail_inputs_s1/`
  - `data/reports/backtests/20260701_232211_20260702_entry_ev_external_hybrid_side_regime_exitcap_tail_inputs_s1/`
- Stateful replays:
  - `data/reports/backtests/20260701_232245_20260702_entry_ev_external_hybrid_side_regime_dirinv_s0p1_replay_s1/`
  - `data/reports/backtests/20260701_232245_20260702_entry_ev_external_hybrid_side_regime_dirinv_s0p25_replay_s1/`
  - `data/reports/backtests/20260701_232246_20260702_entry_ev_external_hybrid_side_regime_exitcap_s0p1_replay_s1/`
  - `data/reports/backtests/20260701_232246_20260702_entry_ev_external_hybrid_side_regime_exitcap_s0p25_replay_s1/`
  - `data/reports/backtests/20260701_232455_20260702_entry_ev_external_hybrid_side_context_dirinv_s0p25_replay_s1/`
- Admission:
  - `data/reports/backtests/20260701_232335_20260702_entry_ev_external_hybrid_side_regime_dirinv_s0p25_admission_s1/`
  - `data/reports/backtests/20260701_232428_20260702_entry_ev_external_hybrid_side_regime_exitcap_s0p1_admission_s1/`
- Support:
  - `data/reports/backtests/20260701_232346_20260702_entry_ev_external_hybrid_side_regime_dirinv_s0p25_support_s1/`
- Trade enrichment:
  - `data/reports/backtests/20260701_232402_20260702_entry_ev_external_hybrid_side_regime_dirinv_s0p25_trade_enrichment_s1/`

## Method

Target source:

```text
data/reports/backtests/20260701_133922_20260701_entry_ev_common_loss_target_diagnostics_s1/common_entry_targets.csv
```

Primary group:

```text
direction_regime = direction + combined_regime
```

Negative-control group:

```text
side_context = direction + combined_regime + session_regime
```

Score:

```text
base_score = pred_base_executable_exit_regret_selector_replguard_preblockgap_confidenceexit_bucket_t0p4
tail_risk = chronological prior target rate for the side/context
adjusted_score = base_score * clip(1 - strength * bucket_supported_tail_risk, 0, 1)
```

Important:

- 対象月のtargetは使わない。fitは常に `target_month` より前の月だけ。
- `global` fallbackはrisk列として残すが、score penaltyには使わない。
- `min_group_support=1` は薄いsupportを許す診断設定。標準採用判断では不利な条件として扱う。

## Risk Distribution

Direction-inversion target, `direction_regime`:

| side | risk mean | p50 | p90 | support mean | bucket share | global share |
|---|---:|---:|---:|---:|---:|---:|
| long | `0.5460` | `0.5526` | `0.8509` | `8.2543` | `0.9233` | `0.0767` |
| short | `0.6426` | `0.6272` | `0.7243` | `2.8554` | `0.7756` | `0.2244` |

Penalty effect:

| score kind | long scale mean | short scale mean | long risk used | short risk used |
|---|---:|---:|---:|---:|
| `side_regime_dirinv_direction_regime_s0p1` | `0.9499` | `0.9491` | `0.5008` | `0.5085` |
| `side_regime_dirinv_direction_regime_s0p25` | `0.8748` | `0.8729` | `0.5008` | `0.5085` |

Fine `side_context` had much thinner bucket coverage:

| side | support mean | bucket share | global share |
|---|---:|---:|---:|
| long | `1.9652` | `0.6256` | `0.3744` |
| short | `0.7267` | `0.3658` | `0.6342` |

## Replay

Compared against 00273 base executable selector:

| run | candidate | total | worst month | trades | max DD | max side share |
|---|---|---:|---:|---:|---:|---:|
| 00273 base | q95/floor5 | `-12.1040` | `-26.7600` | `4` | `26.7600` | `0.7500` |
| 00273 base | q99/floor5 | `-27.4800` | `-26.7600` | `2` | `26.7600` | `0.5000` |
| dir-regime dir-inv s0.1 | q99/floor5 | `-27.5640` | `-26.8440` | `3` | `26.8440` | `0.6667` |
| dir-regime dir-inv s0.1 | q95/floor5 | `-29.5080` | `-26.8440` | `4` | `26.8440` | `0.5000` |
| dir-regime dir-inv s0.25 | q99/floor5 | `+3.1260` | `-0.7200` | `3` | `0.7200` | `1.0000` |
| dir-regime dir-inv s0.25 | q95/floor5 | `-7.2060` | `-4.5420` | `5` | `8.3880` | `0.6000` |
| dir-regime exit-cap s0.1 | q99/floor5 | `+3.1260` | `-0.7200` | `3` | `0.7200` | `1.0000` |
| dir-regime exit-cap s0.1 | q95/floor5 | `-7.2060` | `-4.5420` | `5` | `8.3880` | `0.6000` |
| dir-regime exit-cap s0.25 | q99/floor5 | `+3.1260` | `-0.7200` | `3` | `0.7200` | `1.0000` |
| dir-regime exit-cap s0.25 | q95/floor5 | `-7.2060` | `-4.5420` | `5` | `8.3880` | `0.6000` |
| side-context dir-inv s0.25 | q99/floor5 | `-27.5640` | `-26.8440` | `3` | `26.8440` | `0.6667` |
| side-context dir-inv s0.25 | q95/floor5 | `-29.5080` | `-26.8440` | `4` | `26.8440` | `0.5000` |

Best q99 monthly:

| month | pnl | trades | long | short | max DD |
|---|---:|---:|---:|---:|---:|
| 2025-09 | `0.0000` | `0` | `0` | `0` | `0.0000` |
| 2025-10 | `0.0000` | `0` | `0` | `0` | `0.0000` |
| 2025-11 | `-0.7200` | `1` | `1` | `0` | `0.7200` |
| 2025-12 | `+3.8460` | `2` | `2` | `0` | `0.0840` |

## Support And Admission

Support for `dir-regime dir-inv s0.25`:

| candidate | quantile all | quantile hold | candidate rows | long rows | short rows |
|---|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `30` | `11` | `4` | `4` | `0` |
| q95/floor5/rank90 | `111` | `40` | `8` | `4` | `4` |

Admission:

| candidate | eligible | blockers | total | worst month | trades | max side share |
|---|---|---|---:|---:|---:|---:|
| q99/floor5/rank90 | false | `month_pnl_below_floor;role_trades_low;month_trades_low;side_share_high` | `+3.1260` | `-0.7200` | `3` | `1.0000` |
| q95/floor5/rank90 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` | `-7.2060` | `-4.5420` | `5` | `0.6000` |

Selected policy:

```text
no_trade
```

## Trade Enrichment

`dir-regime dir-inv s0.25`:

| candidate | trades | total | win rate | direction error | exit regret sum | EV overestimate mean | exit capture ratio mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `3` | `+3.1260` | `0.3333` | `0.0000` | `116.8140` | `4.5454` | `0.0568` |
| q95/floor5/rank90 | `5` | `-7.2060` | `0.2000` | `0.2000` | `175.7160` | `7.2430` | `0.0341` |

q99 trades:

| month | direction | regime | session | pnl | tail risk source | exit regret | EV overestimate |
|---|---|---|---|---:|---|---:|---:|
| 2025-11 | long | `range_low_vol` | `ny_late` | `-0.7200` | bucket | `48.9000` | `6.7670` |
| 2025-12 | long | `down_low_vol` | `ny_late` | `-0.0840` | global | `48.7740` | `5.3775` |
| 2025-12 | long | `down_high_vol` | `rollover` | `+3.9300` | global | `19.1400` | `1.4918` |

Reading:

- The head removes the 00273 short tail and sharply reduces EV overestimate.
- It does not solve exit timing: exit regret remains large and exit capture ratio remains low.
- The profitable q99 path is extremely sparse and all-long, so it is not enough for standard policy.

## Decision

Accepted:

- side/regime tail-risk input-generation infrastructure
- `direction_regime` as a useful coarse diagnostic head
- keeping `dir-regime dir-inv s0.25` / `dir-regime exit-cap s0.1` as positive diagnostic baselines

Rejected:

- standardizing the q99 positive result on this fold
- using `side_context` session-level risk as the main branch
- treating `min_group_support=1` as robust evidence
- tuning q99/q95 thresholds further on the same `2025-09..12` fold

Standard policy remains NoTrade.

## Next

1. Validate `direction_regime` tail-risk head on another chronology before any policy promotion.
2. Treat this as a training/selector feature candidate, not a hard policy.
3. Improve exit timing target separately: q99 still has large exit regret despite positive total.
4. Increase external-window support before relaxing admission gates.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_regime_tail_policy_inputs.py tests/test_entry_ev_side_regime_tail_policy_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_regime_tail_policy_inputs`: OK
- direction-regime dir-inv / exit-cap input generation: OK
- direction-regime q99/q95 stateful replays: OK
- side-context negative-control replay: OK
- support/admission/trade enrichment: OK
