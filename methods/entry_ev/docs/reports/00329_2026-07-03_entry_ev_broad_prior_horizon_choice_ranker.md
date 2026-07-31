# Entry EV Broad Prior Horizon Choice Ranker

日時: 2026-07-03 06:32 JST
更新日時: 2026-07-03 06:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00328の次アクションとして、broad duration priorを静的penaltyではなく、chronological horizon-choice ranker/headのfeatureとして使った。
- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py` を追加した。broad train rowsを60/240/720mのhorizon-level examplesへ展開し、target月より前だけで `pnl / delta_vs_60 / executable / tail_loss / beats_60` headを学習する。
- 00328のprior列を各horizon exampleへ付け、`duration_prior_mean_pnl`, `duration_prior_delta_vs_60_mean`, `duration_prior_tail_loss_rate`, `repair_duration_risk_score` などを通常featureとして入れた。
- default complexity (`max_leaf_nodes=8`, `l2=1`) はbest combined `+368.5540`。00328 direct penalty `+363.0870` は超えたが、00326 hpen0.25 `+374.6110` には届かなかった。
- 低複雑度版 (`max_leaf_nodes=4`, `l2=5`) はbest combined `+403.2680`、added PnL `+63.9770` まで伸びた。ただし追加5本で `role_trades_low` が残り、month min `-0.6120`、side-share blockerも残るため、標準policyにはしない。
- tailを強めるだけの感度はbest combined `+364.4940` へ悪化。fallback許可も低複雑度版と同じbestで、coverage不足の本質解決にはならなかった。
- 結論: broad-prior horizon-choice ranker infrastructureはaccepted。低複雑度rankerはdiagnostic bestを更新。ただしstandard policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`
- New tests:
  - `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`
- Default ranker replay:
  - `data/reports/backtests/20260702_212732_20260703_entry_ev_00329_broad_prior_horizon_choice_replay_s1/`
- Tail-strong sensitivity:
  - `data/reports/backtests/20260702_212857_20260703_entry_ev_00329_broad_prior_horizon_choice_replay_tailstrong_s1/`
- Low-complexity / stronger regularization:
  - `data/reports/backtests/20260702_213026_20260703_entry_ev_00329_broad_prior_horizon_choice_replay_reg_s1/`
- Fallback allowed diagnostic:
  - `data/reports/backtests/20260702_213156_20260703_entry_ev_00329_broad_prior_horizon_choice_replay_reg_fallback_s1/`

## Method

Each candidate row is expanded into horizon-level examples:

```text
row -> 60m example
row -> 240m example
row -> 720m example
```

For each target month:

```text
train = broad_train_horizon_examples where month < target_month
target = support-repair candidate horizon examples in target_month
```

Features include:

- row-level score / margin / rank / regime / session / side features
- horizon identity and predicted fixed-horizon PnL
- predicted delta vs 60m
- 00328 broad duration prior columns
- prior context spec and support counts

Targets:

- realized horizon PnL
- realized delta vs 60m
- executable class
- tail-loss class
- beats-60m class

Replay still uses the existing support repair admission gates. No target-month realized PnL is used as a feature.

## Results

| run | best scenario | added | added PnL | combined total | month min | role min | role trade min | remaining extra | blockers |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| default ranker | available p0.5 EV-2/0 tail0.3 model-used `pnl_delta` | `6` | `+29.2630` | `+368.5540` | `-0.6120` | `+0.5354` | `4` | `2` | month, side-share |
| tail-strong | available p0.45 EV-2/0 tail0.25 model-used `pnl_delta_tail` | `6` | `+25.2030` | `+364.4940` | `-0.6120` | `+0.5354` | `4` | `2` | month, side-share |
| low-complexity | available p0.5 EV2 tail0.3 model-used `pnl` | `5` | `+63.9770` | `+403.2680` | `-0.6120` | `+0.5354` | `3` | `3` | month, role-trades, side-share |
| fallback allowed | available p0.45/0.5 EV2 tail0.3 allow-fallback `pnl` | `5` | `+63.9770` | `+403.2680` | `-0.6120` | `+0.5354` | `3` | `3` | month, role-trades, side-share |

Low-complexity best additions:

| role | month | side | decision UTC | horizon | predicted score | pred executable | pred tail | actual |
|---|---|---|---|---:|---:|---:|---:|---:|
| hybrid2025_0912_external | 2025-10 | long | 2025-10-01 21:58 | 720 | `+2.3111` | `0.6139` | `0.2573` | `+10.9530` |
| hybrid2025_0912_external | 2025-11 | short | 2025-11-10 01:35 | 60 | `+2.3420` | `0.6043` | `0.2411` | `+10.4400` |
| refit2025_validation | 2025-07 | short | 2025-07-28 04:10 | 720 | `+3.9724` | `0.6223` | `0.2962` | `+26.4000` |
| refit2025_validation | 2025-08 | short | 2025-08-08 03:27 | 720 | `+2.7232` | `0.5847` | `0.2683` | `+2.9340` |
| refit2025_validation | 2025-08 | long | 2025-08-14 17:28 | 720 | `+3.3697` | `0.5958` | `0.2141` | `+13.2500` |

Remaining weak months in the low-complexity best:

| role | month | PnL | trades | side share |
|---|---|---:|---:|---:|
| fresh2024_validation | 2024-11 | `-0.6120` | `1` | `1.0000` |
| refit2025_validation | 2025-03 | `-0.4730` | `9` | `0.5556` |
| fresh2024_validation | 2024-03 | `-0.3636` | `1` | `1.0000` |

## Diagnostics

Default complexity fixed fresh2024 2024-08 by choosing 60m for the known bad row:

```text
fresh2024 2024-08 long 2024-08-22 03:39
pnl-only:       720m actual -29.1360
pnl_delta:       60m actual  +2.9500
pnl_delta_tail:  60m actual  +2.9500
```

But default complexity still picked a refit2025 2025-08 short 720m loser. Its broad prior was actually positive:

```text
refit2025 2025-08 short 2025-08-13 00:12
720m actual -13.0200
duration prior mean +11.3311
duration prior delta vs 60m +11.7206
tail-loss rate 0.2227
```

This is important: 00328-style duration prior can catch the fresh2024 2024-08 pattern, but not all bad 720m. Some losing 720m rows live inside historically positive 720m contexts.

## Decision

Accepted:

- chronological horizon-level ranker infrastructure
- broad duration prior as model features
- low-complexity / stronger-regularization sensitivity
- support-repair replay integration via generated `pred_hv_*` columns

Rejected:

- default complexity ranker as a standard policy
- tail-strengthening alone as the next fix
- fallback-allowed replay as policy evidence
- treating combined `+403.2680` as standard-ready while role/month/side-share gates still fail

Standard policy remains NoTrade.

## Interpretation

The model quality improved when complexity was reduced. That is evidence that the previous head was still too flexible for the available support-repair target surface. The low-complexity ranker found high-value long-horizon winners and avoided the fresh2024 2024-08 disaster without using realized target-month PnL.

However, the result is not stable enough to standardize:

- role trade support is still low
- two fresh2024 months remain single-trade side-share failures
- month floor still fails
- the score is still over-optimistic for some 720m paths

The next step should not be another static tail threshold. It should be a calibrated lower-bound / downside-aware rank score that preserves high-value 720m winners while explicitly penalizing high uncertainty.

## Next

1. Add a chronological lower-bound score for horizon choice, such as `pred_pnl - k * residual_mae_by_horizon_context - tail_penalty`.
2. Build residual calibration by horizon / side / regime using only prior months.
3. Use support-targeted coverage for fresh2024 2024-03 and 2024-11 instead of globally relaxing fallback.
4. Keep low-complexity ranker as the current diagnostic branch, not a standard policy.
5. Keep standard admission gates unchanged: NoTrade remains the standard policy.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00329 default ranker replay: OK
- 00329 tail-strong sensitivity: OK
- 00329 low-complexity ranker replay: OK
- 00329 fallback allowed diagnostic: OK
