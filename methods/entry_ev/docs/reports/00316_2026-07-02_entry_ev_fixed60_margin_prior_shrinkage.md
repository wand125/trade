# Entry EV Fixed60 Margin Prior Shrinkage

日時: 2026-07-02 19:40 JST
更新日時: 2026-07-02 19:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00315の次アクションとして、00314 family-aware w5のrefit集中改善を、より粗いpriorへ寄せても再現できるか検証した。
- `scripts/experiments/entry_ev_fixed60_uncertainty_margin_policy_inputs.py` に prior shrinkageを追加した。
- shrinkageは `family,direction,combined_regime,session_regime` のchild priorを、`direction,combined_regime,session_regime` のparent priorへ疑似カウントで寄せる。
- w0 controlは `+126.8118` を再現し、preblockgap side-gap継承は維持できた。
- ただしshrinkage replayはbestでも `+107.0324` で、00314 family-aware w5 raw `+139.1098` を大きく下回った。month minは全て `-6.8324` のまま。
- 判断: prior shrinkage実装はaccepted infrastructure。今回の shrinkage policyはrejected。family-aware w5改善は粗いpriorへ寄せると消えるため、標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_fixed60_uncertainty_margin_policy_inputs.py`
- Updated tests:
  - `tests/test_entry_ev_fixed60_uncertainty_margin_policy_inputs.py`
- Input generation:
  - `data/reports/backtests/20260702_101623_20260702_entry_ev_00316_fixed60_margin_shrink_internal_hgb_preblockgap_s1/`
  - `data/reports/backtests/20260702_101623_20260702_entry_ev_00316_fixed60_margin_shrink_hybrid_preblockgap_s1/`
- Replay runs:
  - `data/reports/backtests/20260702_102736_20260702_entry_ev_00316_shrink_s5_w0_replay_s1/`
  - `data/reports/backtests/20260702_102736_20260702_entry_ev_00316_shrink_s2_w1_replay_s1/`
  - `data/reports/backtests/20260702_102736_20260702_entry_ev_00316_shrink_s2_w2_replay_s1/`
  - `data/reports/backtests/20260702_102736_20260702_entry_ev_00316_shrink_s2_w5_replay_s1/`
  - `data/reports/backtests/20260702_103903_20260702_entry_ev_00316_shrink_s5_w1_replay_s1/`
  - `data/reports/backtests/20260702_103903_20260702_entry_ev_00316_shrink_s5_w2_replay_s1/`
  - `data/reports/backtests/20260702_103903_20260702_entry_ev_00316_shrink_s5_w5_replay_s1/`

## Method

Original 00314 margin:

```text
prior_fp_rate = child false-positive count / child fixed60 predicted-positive count
uncertainty_input = prior_fp_rate * max(side_fixed60_pred_pnl, 0)
margin_score = base_entry_score - weight * uncertainty_input
```

Shrinkage:

```text
parent_fp_rate = parent false-positive count / parent fixed60 predicted-positive count
shrunk_fp_rate = (child_false_count + alpha * parent_fp_rate)
                 / (child_pred_positive_count + alpha)
uncertainty_input = shrunk_fp_rate * max(side_fixed60_pred_pnl, 0)
margin_score = base_entry_score - weight * uncertainty_input
```

Tested context:

```text
child:  family,direction,combined_regime,session_regime
parent: direction,combined_regime,session_regime
alpha:  2, 5, 10, 20
weight: 0, 0.5, 1, 2, 5
```

Replay was evaluated under the same raw benchmark lane as 00314:

```text
q95_sg95_rank90_floor5_side_regime_session_month
loss_exit30_cd15
loss multiplier 1.20
short entry-block side EV penalty replacement
preblockgap side-gap quantile inherited from source score kind
```

## Input Effect

Across internal HGB + hybrid families, shrinkage mostly affected short-side risk.

| alpha | weight | side switch mean | score delta mean | max long risk q95 | max short risk q95 |
|---:|---:|---:|---:|---:|---:|
| `2` | `1` | `0.001979` | `-0.006632` | `0.000000` | `0.188351` |
| `2` | `2` | `0.002713` | `-0.011992` | `0.000000` | `0.188351` |
| `2` | `5` | `0.005821` | `-0.024578` | `0.000000` | `0.188351` |
| `5` | `1` | `0.001963` | `-0.006506` | `0.000000` | `0.184384` |
| `5` | `2` | `0.002698` | `-0.011768` | `0.000000` | `0.184384` |
| `5` | `5` | `0.005722` | `-0.024191` | `0.000000` | `0.184384` |
| `10` | `5` | `0.005625` | `-0.023956` | `0.000000` | `0.183932` |
| `20` | `5` | `0.005583` | `-0.023797` | `0.000000` | `0.180723` |

Reading:

- The shrinkage feature is active but modest.
- Short-side q95 risk is non-zero, while long-side q95 is effectively zero in this branch.
- This is consistent with 00315: the useful 00314 delta came from removing a few refit2025 rows rather than broad side/risk recalibration.

## Replay Sweep

| score kind | total | trades | month min | role min | max DD | reading |
|---|---:|---:|---:|---:|---:|---|
| 00314 w0 control | `+126.8118` | `254` | `-6.8324` | `+0.5354` | `30.8714` | baseline |
| 00314 family-aware w5 | `+139.1098` | `249` | `-6.8324` | `+0.5354` | `30.8714` | diagnostic best raw |
| shrink s5 w0 | `+126.8118` | `254` | `-6.8324` | `+0.5354` | `30.8714` | no-op control passes |
| shrink s2 w1 | `+95.6904` | `246` | `-6.8324` | `+0.5354` | `30.8714` | worse |
| shrink s2 w2 | `+105.1664` | `243` | `-6.8324` | `+0.5354` | `21.1634` | worse, lower DD |
| shrink s2 w5 | `+107.0324` | `242` | `-6.8324` | `+0.5354` | `21.1634` | best shrink, still worse |
| shrink s5 w1 | `+94.9464` | `247` | `-6.8324` | `+0.5354` | `30.8714` | worse |
| shrink s5 w2 | `+105.1664` | `243` | `-6.8324` | `+0.5354` | `21.1634` | worse |
| shrink s5 w5 | `+106.3364` | `242` | `-6.8324` | `+0.5354` | `21.1634` | worse |

All replay rows remain NoTrade:

```text
month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high
```

## Downstream Decision

Hold-extension / position-quality overlay / support-aware admission were not rerun for the shrinkage branches.

Reason:

- The raw replay gate failed before downstream integration.
- Best shrink raw `+107.0324` is below baseline `+126.8118` and below 00314 family-aware w5 `+139.1098`.
- Month floor is unchanged at `-6.8324`.
- Pushing a raw-worse branch through hold-extension/overlay would increase search overfitting risk without a stronger input signal.

This is consistent with the current research rule: do not spend downstream optimization budget on a score-head branch that fails the no-op control + raw replay comparison.

## Decision

Accepted:

- prior shrinkage implementation for fixed60 uncertainty margin
- score-kind naming with child/parent/alpha labels
- shrinkage diagnostics columns, including parent prior support and shrunk fp rate
- w0 control for shrinkage score kinds

Rejected:

- current `family,direction,regime,session -> direction,regime,session` shrinkage as a policy branch
- treating lower max drawdown at `s2/s5 w2/w5` as sufficient when total and month floor are worse
- running downstream hold-extension/overlay just because the feature is more conservative

Standard policy remains NoTrade.

## Next

1. Move from context-count shrinkage to calibrated EV uncertainty that is trained/evaluated OOF and used as a continuous feature, not a hard family/context penalty.
2. Directly attack support-limited negative months and side-share blockers instead of only removing candidate rows.
3. Keep 00314 family-aware w5 as diagnostic best, but do not treat it as broad generalization evidence until nonrefit support appears.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_fixed60_uncertainty_margin_policy_inputs.py tests/test_entry_ev_fixed60_uncertainty_margin_policy_inputs.py`: OK
- `uv run python -m unittest tests.test_entry_ev_fixed60_uncertainty_margin_policy_inputs`: OK
- `uv run python -m unittest tests.test_entry_ev_fixed60_uncertainty_margin_policy_inputs tests.test_docs_reports`: OK
- `git diff --check`: OK
- fixed60 margin shrink input generation: OK
- shrink raw replay sweep: OK
