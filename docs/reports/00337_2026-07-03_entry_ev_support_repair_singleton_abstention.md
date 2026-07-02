# Entry EV Support Repair Singleton Abstention

日時: 2026-07-03 08:39 JST
更新日時: 2026-07-03 08:39 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00336で確認したsingleton negativeを、listwise rerankingではなくobservable abstentionとして診断するスクリプトを追加した。
- 対象は00336のcurrent selected additions。actual PnLは評価にだけ使い、abstention条件には `quota_group_is_singleton`, horizon, broad prior, predicted PnL, predicted fixed-best horizonだけを使う。
- baseline bestでは、唯一のsingletonは `hybrid2025_0912_external 2025-10 long +10.9530`。`singleton_any` はこれを削ってadded PnLを `+60.8530 -> +49.9000` に悪化させる。
- EV -2では、唯一のsingleton negative `fresh2024_validation 2024-08 long -29.1360` を、`720m prior mean < 0`, `720m prior tail >= 0.35`, `720m prior risk >= 5`, `pred_pnl < 2`, `pred_fixed_best_horizon=60m` の各observable ruleが弾けた。
- EV -2の条件付きabstentionはadded PnLを `+31.7170 -> +60.8530`、combinedを `+371.0080 -> +400.1440` に戻す。ただしこれはbaseline best相当へ戻すだけで、standard blockersは `month_pnl_below_floor,role_trades_low,side_share_high` のまま残る。
- 判断: singleton abstention diagnosticsはaccepted infrastructure。`singleton_any` はpositive singletonも削るためreject。risk条件付きabstentionは有望な診断信号だが、まだ標準policyではない。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_support_repair_singleton_abstention_diagnostics.py`
- Added tests:
  - `tests/test_entry_ev_support_repair_singleton_abstention_diagnostics.py`
- Baseline best singleton abstention diagnostics:
  - `data/reports/backtests/20260702_233935_20260703_entry_ev_00337_support_repair_singleton_abstention_best_s1/`
- EV -2 singleton abstention diagnostics:
  - `data/reports/backtests/20260702_233935_20260703_entry_ev_00337_support_repair_singleton_abstention_evm2_s1/`

Outputs:

```text
singleton_abstention_summary.csv
singleton_abstention_flagged_rows.csv
singleton_abstention_monthly_metrics.csv
config.json
```

## Method

The diagnostic starts from:

```text
support_repair_listwise_teacher_examples.csv
```

It keeps only:

```text
current_replay_selected == true
```

Then it recomputes monthly metrics after removing rows flagged by each abstention rule.

Abstention rules:

```text
none
singleton_any
singleton_720_prior_mean_neg
singleton_720_prior_tail_ge0p35
singleton_720_prior_mean_neg_tail_ge0p35
singleton_720_prior_risk_ge5
singleton_720_pred_pnl_lt2
singleton_720_pred_best_60m
```

Important boundary:

- actual PnL is never used as an abstention condition.
- actual PnL is used only to evaluate flagged / kept rows and recomputed monthly metrics.
- This is still a small-surface diagnostic, not a trained policy.

## Results

Baseline best scenario:

| rule | abstained | abstained actual | kept added PnL | combined | blockers |
|---|---:|---:|---:|---:|---|
| none | `0` | `0.0000` | `+60.8530` | `+400.1440` | month / role-trades / side-share |
| singleton_any | `1` | `+10.9530` | `+49.9000` | `+389.1910` | month / role-trades / side-share |
| risk-conditioned rules | `0` | `0.0000` | `+60.8530` | `+400.1440` | month / role-trades / side-share |

EV -2 scenario:

| rule | abstained | abstained actual | kept added PnL | combined | blockers |
|---|---:|---:|---:|---:|---|
| none | `0` | `0.0000` | `+31.7170` | `+371.0080` | role-total / month / side-share |
| singleton_any | `1` | `-29.1360` | `+60.8530` | `+400.1440` | month / role-trades / side-share |
| singleton_720_prior_mean_neg | `1` | `-29.1360` | `+60.8530` | `+400.1440` | month / role-trades / side-share |
| singleton_720_prior_tail_ge0p35 | `1` | `-29.1360` | `+60.8530` | `+400.1440` | month / role-trades / side-share |
| singleton_720_prior_mean_neg_tail_ge0p35 | `1` | `-29.1360` | `+60.8530` | `+400.1440` | month / role-trades / side-share |
| singleton_720_prior_risk_ge5 | `1` | `-29.1360` | `+60.8530` | `+400.1440` | month / role-trades / side-share |
| singleton_720_pred_pnl_lt2 | `1` | `-29.1360` | `+60.8530` | `+400.1440` | month / role-trades / side-share |
| singleton_720_pred_best_60m | `1` | `-29.1360` | `+60.8530` | `+400.1440` | month / role-trades / side-share |

Flagged EV -2 singleton:

| role | month | side | actual 720m | fixed 60m actual | fixed 240m actual | 720m prior mean | 720m prior tail | 720m prior risk | predicted 720m PnL | pred fixed best |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fresh2024_validation | 2024-08 | long | `-29.1360` | `+2.9500` | `+4.8500` | `-3.4993` | `0.4145` | `9.9773` | `+1.2973` | `60m` |

Interpretation:

- `singleton_any` is too blunt. It deletes a profitable singleton in baseline best.
- The risk-conditioned rules are more promising because they do not delete the best positive singleton but do delete the EV -2 fresh negative singleton.
- The improvement is a degradation guard, not a standard-policy pass. After abstention, the metrics return to the 00335/00336 best-like state and still fail standard admission.

## Decision

- `entry_ev_support_repair_singleton_abstention_diagnostics.py`: accepted infrastructure.
- `singleton_any`: reject.
- Risk-conditioned singleton abstention: diagnostic signal, not standard policy.
- Standard policy remains NoTrade.

## Next

1. Broaden singleton abstention validation beyond these two singleton cases before policy use.
2. Treat `singleton_720_prior_mean_neg_tail_ge0p35` as the cleanest initial candidate because it combines prior direction and tail evidence.
3. Add fresh/thin month candidate generation so abstaining a bad singleton does not leave support blockers unresolved.
4. Keep all rules observable-time safe; actual PnL remains evaluation / teacher only.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_singleton_abstention_diagnostics.py tests/test_entry_ev_support_repair_singleton_abstention_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_singleton_abstention_diagnostics`: OK
- best / EV -2 singleton abstention diagnostics run: OK
