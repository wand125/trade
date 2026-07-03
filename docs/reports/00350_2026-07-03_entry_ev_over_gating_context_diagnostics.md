# Entry EV Over-Gating Context Diagnostics

日時: 2026-07-03 11:59 JST
更新日時: 2026-07-03 11:59 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00348/00349でglobal hard gate / soft penaltyがno-opまたは悪化だったため、risk ruleが「損失を捕まえる効果」と「勝ち追加候補を巻き込む害」を同時に見えるover-gating診断を追加した。
- `entry_ev_over_gating_diagnostics.py` を追加し、00349のsummary/additions/candidate filesを横断して、top/near-best replay scenarioごとにrule tradeoff、context別tradeoff、selected addition巻き込みcaseをCSV化した。
- 対象focusは `242` scenario。内訳はcombined `+400.1440` が144、`+399.8040` が84、`+389.5310` が12、`+389.1910` が2。
- 結論: tail probabilityはcontextによって損失候補を非常にきれいに捕まえるが、best selected additionsでは発火0。harmful/residual/720m系は損失候補も捕まえる一方、best/near-best selected winnersを直接巻き込む。従って次はglobal cutoffではなく、context/horizon別のcandidate generation / abstention confidence / calibrationへ進む。
- 標準policyはNoTradeのまま。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_over_gating_diagnostics.py`

Added tests:

- `tests/test_entry_ev_over_gating_diagnostics.py`

Run:

- `data/reports/backtests/20260703_025910_20260703_entry_ev_00350_over_gating_context_diagnostics/`

Main outputs:

- `over_gating_focus_scenarios.csv`
- `over_gating_scenario_rule_summary.csv`
- `over_gating_rule_tradeoff_summary.csv`
- `over_gating_context_rule_summary.csv`
- `over_gating_selected_cases.csv`
- `config.json`

## Method

Inputs:

- 00349 `broad_prior_horizon_choice_replay_summary.csv`
- 00349 `broad_prior_horizon_choice_additions.csv`
- 00349 `ranker_replay_candidates_*.csv`

Scenario key:

- `row_scope`
- `prob_threshold`
- `ev_threshold`
- `tail_prob_threshold`
- `require_model_used`
- `ranker_score_mode`
- `ranker_abstention_rule`
- `positive_pnl_gate_rule`
- `positive_pnl_penalty_label`

For each focus scenario and rule, the diagnostic records:

- positive predicted PnL candidate PnL
- flagged loss count/PnL
- flagged win count/PnL
- pointwise gate delta
- selected addition count/PnL
- selected flagged loss/win count/PnL
- selected winner over-gating flag

Actual PnL is used only for diagnostics.

## Results

Best scenario:

- scenario rank `1`
- `pnl / none / available_candidates`
- `prob_threshold=0.45`, `ev_threshold=2`, `tail_prob_threshold=0.3`
- added `5`
- added PnL `+60.8530`
- combined `+400.1440`
- blockers remain `month_pnl_below_floor,role_trades_low,side_share_high`

Best-scenario rule tradeoff:

| rule | flagged PnL | flagged losses | loss PnL | flagged wins | win PnL | selected flagged wins | selected flagged win PnL | reading |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `tail_prob_ge_0p30` | `0.0000` | `0` | `0.0000` | `0` | `0.0000` | `0` | `0.0000` | bestではno-op |
| `harmful_prob_ge_0p30` | `+49.4224` | `3` | `-40.2876` | `7` | `+89.7100` | `3` | `+49.5600` | selected winnersを巻き込む |
| `residual_tail_miss_ge_0p10` | `+85.1660` | `9` | `-51.1260` | `22` | `+136.2920` | `5` | `+60.8530` | selected winnersを全て巻き込む |
| `positive_bias_and_tail_miss_ge_0p10` | `+43.4600` | `0` | `0.0000` | `4` | `+43.4600` | `1` | `+12.7200` | bestでは損失を捕まえず勝ちだけ削る |
| `horizon_720m` | `+56.0760` | `9` | `-51.1260` | `18` | `+107.2020` | `4` | `+50.4130` | 720m一律抑制は危険 |

Near-best aggregate:

| rule | scenario count | flagged PnL | loss PnL | win PnL | selected flagged wins | selected flagged win PnL |
|---|---:|---:|---:|---:|---:|---:|
| `tail_prob_ge_0p30` | `242` | `-59216.3688` | `-61005.8808` | `+1789.5120` | `0` | `0.0000` |
| `harmful_prob_ge_0p30` | `242` | `-25989.5096` | `-47842.0416` | `+21852.5320` | `726` | `+11993.5200` |
| `residual_tail_miss_ge_0p10` | `242` | `-28588.5116` | `-58580.0136` | `+29991.5020` | `1124` | `+14548.6040` |
| `positive_bias_and_tail_miss_ge_0p10` | `242` | `-40251.5056` | `-49634.0856` | `+9382.5800` | `256` | `+3083.0000` |

Context readings:

- `tail_prob_ge_0p30` is clean in some high-risk contexts:
  - `720m short / up_normal_vol / asia / one_failed_strict_stage`: flagged actual PnL `-5194.7040`, loss count `81`, win count `0`, selected winner damage `0`.
  - `720m short / down_normal_vol / london / one_failed_strict_stage`: flagged actual PnL `-1513.6752`, loss PnL `-1591.3152`, win PnL `+77.6400`, selected winner damage `0`.
- `harmful_prob_ge_0p30` is over-gated in profitable contexts:
  - `720m short / range_low_vol / asia / one_failed_strict_stage`: flagged actual PnL `+36.2976`, win PnL `+1003.2000`, selected flagged win PnL `+1003.2000`.
  - `720m long / down_normal_vol / ny_late / one_failed_strict_stage`: flagged actual PnL `+1287.7600`, loss count `0`, selected flagged win PnL `+483.3600`.

Selected winner cases:

- `harmful_prob_ge_0p30` flags profitable selected additions:
  - `refit2025_validation 2025-07 short 720m`: actual `+26.4000`, tail prob `0.2962`, harmful prob `0.4824`, context `range_low_vol/asia`.
  - `refit2025_validation 2025-08 long 720m`: actual `+12.7200`, tail prob `0.2141`, harmful prob `0.3948`, context `down_normal_vol/ny_late`.
  - `hybrid2025_0912_external 2025-11 short 60m`: actual `+10.4400`, tail prob `0.2411`, harmful prob `0.4101`, context `up_normal_vol/asia`.
- `positive_bias_and_tail_miss_ge_0p10` flags:
  - `refit2025_validation 2025-08 long 720m`: actual `+12.7200`.
  - `hybrid2025_0912_external 2025-10 long 60m`: actual `+0.3400`.
- `tail_prob_ge_0p30` flags no selected additions in the focus set.

## Decision

- `entry_ev_over_gating_diagnostics.py`: accepted infrastructure.
- `over_gating_*` artifact set: accepted diagnostic output.
- Global harmful/residual/720m risk rules remain rejected as policy gates because they remove selected winners in best/near-best scenarios.
- `tail_prob_ge_0p30` is not a direct global policy either, but it is a useful context-specific risk signal because it captures large losing clusters without selected-winner damage in the current focus set.
- Standard policy remains NoTrade.

## Next

1. Use `tail_prob_ge_0p30` as a context-prior signal, not as global gate. Start with `720m short / up_normal_vol / asia / one_failed_strict_stage` and `720m short / down_normal_vol / london / one_failed_strict_stage`.
2. Split harmful/residual calibration by horizon/side/regime/session before using it in abstention or repair score.
3. Add a context-specific abstention confidence diagnostic: allow a risk rule only if prior context shows loss capture with low selected-winner damage.
4. Keep structural blockers in view: the best scenario still fails `month_pnl_below_floor`, `role_trades_low`, and `side_share_high`.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_over_gating_diagnostics.py tests/test_entry_ev_over_gating_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_over_gating_diagnostics`: OK
- 00350 over-gating context diagnostics: OK
