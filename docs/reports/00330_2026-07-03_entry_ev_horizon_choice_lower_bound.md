# Entry EV Horizon Choice Lower-Bound Residual Score

日時: 2026-07-03 06:54 JST
更新日時: 2026-07-03 06:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00329の次アクションとして、horizon/context別のprior residualからlower-bound scoreを作った。
- `entry_ev_broad_prior_horizon_choice_replay.py` に `pnl_lower`, `pnl_delta_lower`, `pnl_delta_tail_lower` を追加した。
- residual priorはtarget月より前のhorizon prediction errorだけで作る。metricsは `bias / mae / rmse / overestimate_rate / tail_miss_rate`。
- 公平な比較のため、residual prior列はデフォルトではrankerの学習featureに入れず、score-only / diagnosticsとして扱うようにした。
- 強いpenalty、軽いpenalty、微小penaltyを試したが、いずれも00329 low-complexity baselineを上回らなかった。
- 結論: lower-bound residual scoring infrastructureはaccepted。ただし現weightのlower-bound scoreはpolicy候補としてreject。標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`
- Updated tests:
  - `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`
- Strong residual penalty:
  - `data/reports/backtests/20260702_214901_20260703_entry_ev_00330_broad_prior_horizon_choice_lower_bound_scoreonly_s1/`
- Light residual penalty:
  - `data/reports/backtests/20260702_215126_20260703_entry_ev_00330_broad_prior_horizon_choice_lower_bound_scoreonly_light_s1/`
- Tiny residual penalty:
  - `data/reports/backtests/20260702_215327_20260703_entry_ev_00330_broad_prior_horizon_choice_lower_bound_scoreonly_tiny_s1/`

## Method

For each horizon example:

```text
error = horizon_pred_fixed_pnl - horizon_actual_pnl
```

For each target row/month, residual prior is selected from prior months only, using a fallback context chain:

```text
horizon_bucket, side, combined_regime, session_regime, near_miss_bucket
horizon_bucket, side, combined_regime, session_regime
horizon_bucket, side, combined_regime
horizon_bucket, side, session_regime
horizon_bucket, combined_regime, session_regime
horizon_bucket, side
horizon_bucket
global
```

Lower-bound penalty:

```text
penalty =
  mae_weight * residual_prior_mae
  + bias_weight * max(residual_prior_bias, 0)
  + tail_miss_weight * residual_prior_tail_miss_rate
```

New score modes:

```text
pnl_lower            = pnl_score - penalty
pnl_delta_lower      = pnl_delta_score - penalty
pnl_delta_tail_lower = pnl_delta_tail_score - penalty
```

Important implementation decision:

- residual prior columns are not default ranker features.
- they are default score/diagnostic inputs only.
- this avoids changing the learned ranker while testing whether lower-bound scoring improves horizon choice.

## Results

| run | mode | best combined | added PnL | added count | month min | min remaining trades | min hurdle | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| strong | `pnl` baseline | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `2` | `1.4486` | `0` |
| strong | `pnl_delta_lower` | `+340.6110` | `+1.3200` | `1` | `-0.7200` | `6` | `1.8256` | `0` |
| strong | `pnl_lower` | `+339.2910` | `+0.0000` | `0` | `-0.7200` | `8` | `2.1686` | `0` |
| strong | `pnl_delta_tail_lower` | `+339.2910` | `+0.0000` | `0` | `-0.7200` | `8` | `2.1686` | `0` |
| light | `pnl` baseline | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `2` | `1.4486` | `0` |
| light | `pnl_delta_lower` | `+376.8110` | `+37.5200` | `4` | `-0.6120` | `2` | `1.4486` | `0` |
| light | `pnl_lower` | `+366.7520` | `+27.4610` | `6` | `-19.8260` | `2` | `2.1686` | `0` |
| light | `pnl_delta_tail_lower` | `+365.6910` | `+26.4000` | `1` | `-0.7200` | `2` | `2.1686` | `0` |
| tiny | `pnl` baseline | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `2` | `1.4486` | `0` |
| tiny | `pnl_lower` | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `2` | `1.4486` | `0` |
| tiny | `pnl_delta_lower` | `+400.6740` | `+61.3830` | `5` | `-0.6120` | `2` | `1.4486` | `0` |
| tiny | `pnl_delta_tail_lower` | `+390.0610` | `+50.7700` | `5` | `-0.6120` | `2` | `1.4486` | `0` |

Weights:

| run | mae | positive bias | tail miss |
|---|---:|---:|---:|
| strong | `0.25` | `0.25` | `5.0` |
| light | `0.05` | `0.05` | `1.0` |
| tiny | `0.01` | `0.01` | `0.2` |

Horizon usage across additions:

| run | mode | 60m | 240m | 720m | total added rows PnL |
|---|---|---:|---:|---:|---:|
| baseline | `pnl` | `56` | `12` | `189` | `+2077.1300` |
| light | `pnl_delta_lower` | `161` | `12` | `75` | `+841.7940` |
| light | `pnl_delta_tail_lower` | `120` | `12` | `66` | `+677.3760` |
| light | `pnl_lower` | `86` | `8` | `100` | `+1078.9720` |
| tiny | `pnl_delta_lower` | `83` | `12` | `189` | `+1899.2412` |
| tiny | `pnl_delta_tail_lower` | `111` | `12` | `138` | `+1447.9560` |

## Diagnostics

The lower-bound penalty does what it was designed to do: it distrusts high-error / high-tail-miss horizons, especially 720m.

But in the current support-repair target surface, 720m still contains too much of the profitable repair mass. Penalizing it globally by residual uncertainty removes winners faster than it improves the weak months.

Key observations:

- strong penalty nearly shuts off the lower-bound additions.
- light penalty shifts many choices from 720m to 60m and loses PnL.
- tiny penalty is effectively a no-op for `pnl_lower`, and slightly worse for delta/tail lower scores.
- no lower-bound mode passes selector gates.
- the same standard blockers remain: month floor, role trade support, side-share concentration.

This means the current problem is not only EV overconfidence. It is also support allocation: the model still needs enough good extra entries in the thin months without destroying profitable long-horizon candidates elsewhere.

## Decision

Accepted:

- chronological residual prior computation by horizon/context
- lower-bound score modes as diagnostics
- residual diagnostics in pivoted horizon columns
- score-only default behavior for residual prior columns
- regression tests for prior-month-only residuals and score-only defaults

Rejected as policy evidence:

- strong lower-bound score
- light lower-bound score
- treating residual uncertainty as a global 720m suppressor
- using tiny lower-bound equivalence as improvement

Standard policy remains NoTrade.

## Interpretation

The residual prior is useful, but not as a direct subtractive score under the current objective.

The useful part is diagnostic:

- which horizon/context has systematic overestimate bias
- where 720m is genuinely dangerous
- where the model is uncertain but still historically profitable

The direct lower-bound score is too blunt because it cannot distinguish:

```text
high residual because the context is noisy and bad
high residual because the context has large but profitable dispersion
```

So the next step should not be increasing the lower-bound penalty. It should be a target that separates harmful overestimation from profitable high-variance 720m opportunities.

## Next

1. Keep 00329 low-complexity ranker as the current diagnostic best.
2. Use residual prior metrics as diagnostics/features, not as default score penalty.
3. Build a targeted harmful-overestimate label:
   - overestimated by model
   - chosen horizon underperforms 60m or target hurdle
   - not compensated by month/role support
4. Add support-repair objective terms that explicitly reward filling thin months and opposite-side support, instead of relying only on horizon-level EV.
5. Continue standard admission unchanged: NoTrade unless multi-window gates pass.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00330 strong lower-bound score-only replay: OK
- 00330 light lower-bound score-only replay: OK
- 00330 tiny lower-bound score-only replay: OK
