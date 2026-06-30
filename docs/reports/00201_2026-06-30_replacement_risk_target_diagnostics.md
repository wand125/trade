# Replacement Risk Target Diagnostics

日時: 2026-06-30 11:19 JST
更新日時: 2026-06-30 11:23 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00200の結論に従い、`model-trade-delta` の `only_candidate` shortをreplacement risk target化した。
- `short_replacement_risk_target_diagnostics.py` を追加し、`replacement_pnl`, `replacement_is_loss`, `replacement_large_loss` を出力するようにした。
- `global_gap5_budget0` のreplacement shortは全12ヶ月では `255 trades / +210.5324` だが、late 2025-08..12では `67 trades / -286.9878`。同じreplacementでも期間regimeで性質が反転する。
- late `global_gap5_budget0` では `pred_taken_profit_barrier_hit < 0.5` が `-291.8810` を覆い、残りは `+4.8932`。ただし全12ヶ月ではこの条件のcovered PnLが `+144.2660` で、前半の良いreplacementを大量に消す。
- `pred_taken_ev < 15` は疎だが、全12ヶ月 `-87.9540`、late `-83.8596` と一貫して悪いreplacementに寄った。次のdynamic hook候補としては、広い `profit_hit` gateよりこちらが低容量。
- 結論: replacement risk target化は有効。次は `pred_taken_ev < 15`、または `profit_hit < 0.5` を prior deterioration trigger後だけに限定してdynamic backtestする。

## Artifacts

- Replacement risk diagnostics: `data/reports/backtests/20260630_111800_short_replacement_risk_target_diagnostics/`

Inputs:

- `global_gap5_budget0`: `data/reports/backtests/20260630_011534_global_gap5_budget0_vs_baseline_delta/`
- `global_gap0_budget0`: `data/reports/backtests/20260630_011435_global_gap0_budget0_vs_baseline_delta/`
- `focus_or052_vs_gap5`: `data/reports/backtests/20260630_020334_20260630_110700_short_focus_entry_union_vs_gap5_delta/`
- `focus_rank053_vs_gap5`: `data/reports/backtests/20260630_020553_20260630_111700_short_focus_rank053_vs_gap5_delta/`

## Method

Filter:

```text
delta_status = only_candidate
direction = short
```

Targets:

```text
replacement_pnl = candidate_adjusted_pnl
replacement_is_loss = replacement_pnl < 0
replacement_large_loss = replacement_pnl <= -10
replacement_ev_overestimate_vs_pnl = pred_taken_ev - replacement_pnl
```

This is a replacement-risk preflight. Blocking covered replacement rows can still admit another replacement trade, so this is not yet a standard policy result.

## Target Summary

| candidate | window | rows | total PnL | losses | large losses | loss PnL | win PnL |
|---|---|---:|---:|---:|---:|---:|---:|
| `global_gap5_budget0` | all 2025-01..12 | `255` | `+210.5324` | `133` | `26` | `-961.7796` | `+1172.3120` |
| `global_gap5_budget0` | late 2025-08..12 | `67` | `-286.9878` | `50` | `12` | `-457.6968` | `+170.7090` |
| `global_gap5_budget0` | late 2025-09..12 | `50` | `-264.2848` | `37` | `11` | `-408.0408` | `+143.7560` |
| `global_gap0_budget0` | all 2025-01..12 | `87` | `+74.0036` | `43` | `13` | `-364.8024` | `+438.8060` |
| `global_gap0_budget0` | late 2025-08..12 | `16` | `-38.6214` | `9` | `4` | `-92.7084` | `+54.0870` |
| `focus_or052_vs_gap5` | late 2025-08..12 | `5` | `-81.6360` | `5` | `3` | `-81.6360` | `0.0000` |
| `focus_rank053_vs_gap5` | late 2025-08..12 | `2` | `-34.9800` | `2` | `2` | `-34.9800` | `0.0000` |

## Condition Findings

`global_gap5_budget0`, late 2025-08..12:

| condition | covered rows | covered PnL | uncovered PnL | loss PnL coverage |
|---|---:|---:|---:|---:|
| `profit_hit_lt0p5` | `59` | `-291.8810` | `+4.8932` | `0.9756` |
| `pred_ev_lt20` | `37` | `-231.0940` | `-55.8938` | `0.7321` |
| `wait_regret_ge4` | `28` | `-155.2766` | `-131.7112` | `0.5989` |
| `focus_range_low_ny_overlap` | `8` | `-86.5792` | `-200.4086` | `0.1937` |
| `pred_ev_lt15` | `3` | `-83.8596` | `-203.1282` | `0.1832` |

`global_gap5_budget0`, all 2025-01..12:

| condition | covered rows | covered PnL | uncovered PnL | loss PnL coverage |
|---|---:|---:|---:|---:|
| `pred_ev_lt15` | `8` | `-87.9540` | `+298.4864` | `0.1108` |
| `focus_side_gap_le0` | `6` | `-75.0684` | `+285.6008` | `0.0792` |
| `profit_hit_lt0p5` | `218` | `+144.2660` | `+66.2664` | `0.9060` |
| `wait_regret_ge4` | `99` | `+214.1468` | `-3.6144` | `0.5070` |

The late-only `profit_hit_lt0p5` result is strong, but it is not stable across the full year. `pred_ev_lt15` is smaller but directionally stable in this diagnostic.

Worst late `global_gap5_budget0` contexts:

| context | rows | total PnL | loss count | large losses |
|---|---:|---:|---:|---:|
| `up_low_vol / ny_overlap` | `3` | `-103.5756` | `3` | `2` |
| `range_low_vol / ny_overlap` | `8` | `-86.5792` | `7` | `3` |
| `range_low_vol / asia` | `23` | `-82.6692` | `19` | `2` |

## Interpretation

- Replacement risk is not a static context property. `global_gap5_budget0` replacement is profitable over all 2025 but sharply negative in late 2025.
- Wide gates such as `profit_hit_lt0p5` or `wait_regret_ge4` are only acceptable after a prior deterioration trigger. Without that, they remove many good early replacements.
- `pred_ev_lt15` is more conservative and negative in both all-window and late-window diagnostics, but support is only 8 all-year rows. It is a candidate hook, not evidence of a robust policy.
- The next policy should be two-stage:
  - first, detect bad replacement regime with prior-only deterioration,
  - then, inside that regime, block low predicted-EV replacement candidates.

## Decision

- `short_replacement_risk_target_diagnostics.py` is accepted diagnostic infrastructure.
- Do not adopt `profit_hit_lt0p5` globally.
- Keep `pred_ev_lt15` as a low-capacity dynamic hook candidate.
- Next:
  - add a replacement-risk match mode to `side_context_interaction_guard_apply.py`, or a separate apply script, for `signal_short_raw_gap OR replacement_low_ev_after_trigger`;
  - evaluate it with the existing `gap5/budget0 -> gap0/budget0` deterioration trigger or a prior-only late-regime trigger.

## Verification

- `python3 -m py_compile scripts/experiments/short_replacement_risk_target_diagnostics.py tests/test_short_replacement_risk_target_diagnostics.py`: OK
- `python3 -m unittest tests.test_short_replacement_risk_target_diagnostics tests.test_short_budget_replacement_trade_audit tests.test_short_budget_entry_signal_audit tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 16 tests
- `git diff --check`: OK
- Replacement risk diagnostics artifact generated: OK
