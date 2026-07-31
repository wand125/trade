# Near Top Risk Selection

日時: 2026-06-28 21:28 JST
更新日時: 2026-06-28 21:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の `日時` を参照する。

## 目的

前回の結論は、`long:ny_late` を単体ruleとして採用するのではなく、validation topからの許容劣化幅とrisk reductionを同時に扱うselection基準へ進めることだった。今回は `model-candidate-selection` に near-top risk ranking を追加し、直近のlong rule validation gridへ適用した。

## 実装

`model-candidate-selection` に次を追加した。

- `--candidate-rank-mode pnl|near_top_risk`
- `--near-top-cost-pnl-tolerance`
- `--near-top-group-loss-weight`
- `--near-top-drawdown-weight`
- `--near-top-ev-overestimate-weight`
- `--near-top-exit-regret-weight`
- `--near-top-actual-miss-weight`
- `--near-top-side-share-weight`

defaultは `pnl` で、従来の順位を変えない。`near_top_risk` では、eligible候補のbest cost min PnLから `near_top_cost_pnl_tolerance` 以内にある候補をnear-topとして扱い、その範囲ではrisk proxyを小さい順に優先する。

Composite risk score:

```text
group_loss_weight * group_loss_penalty
+ drawdown_weight * max_drawdown_max_all
+ ev_overestimate_weight * ev_overestimate_vs_realized_mean_max_all
+ exit_regret_weight * exit_regret_mean_max_all
+ actual_miss_weight * actual_profit_barrier_miss_rate_smoothed_max_all
+ side_share_weight * max_side_trade_share_max_all
```

## Validation Setup

Input:

- hard block sweeps: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_local_sweep/`
- extra margin sweeps: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_local_sweep/`
- folds: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- selection gates: `min_folds=4`, `min_trades_per_fold=10`, `max_forced_exit_rate=0.05`, `max_drawdown=200`, `min_cost_adjusted_pnl_per_fold=0`, `max_side_trade_share=0.85`
- near-top tolerance: `5.0`

## Composite Risk Result

Composite risk weightsは `group_loss=1`, `drawdown=1`, `EV overestimate=1`, `exit regret=1`, `actual miss=100`, `side share=100`。

Hard block:

| rank | rule | min rank | min pnl | sum pnl | gap | risk score | max DD | group loss | EV over max |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | none | `0.5` | `81.5352` | `396.9782` | `0.0000` | `448.1983` | `60.0744` | `227.6878` | `16.9756` |
| 2 | `long:ny_late` | `0.5` | `78.0572` | `375.5202` | `3.4780` | `484.1204` | `60.0744` | `249.5330` | `17.8068` |
| 3 | `long:ny_late` | `0.0` | `79.7192` | `370.9706` | `1.8160` | `485.7224` | `58.9488` | `252.3560` | `17.5246` |

Extra margin:

| rank | rule | min rank | min pnl | sum pnl | gap | risk score | max DD | group loss | EV over max |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | none | `0.5` | `81.5352` | `396.9782` | `0.0000` | `448.1983` | `60.0744` | `227.6878` | `16.9756` |
| 2 | `long:ny_late:+10` | `0.5` | `78.0572` | `365.1372` | `3.4780` | `484.5242` | `60.0744` | `249.5330` | `18.0087` |
| 3 | `long:ny_late:+5` | `0.5` | `78.0572` | `365.1372` | `3.4780` | `484.5242` | `60.0744` | `249.5330` | `18.0087` |
| 4 | `long:ny_late:+10` | `0.0` | `79.7192` | `360.6406` | `1.8160` | `486.1224` | `58.9488` | `252.3560` | `17.7246` |

Composite riskではruleなしが引き続きtop。`long:ny_late` はnear-top内には残るが、group loss、EV overestimate、exit regret、side concentrationが悪化するため保守候補としては選ばれない。

## Drawdown Only Sensitivity

`near_top_drawdown_weight=1`、その他weight `0` の極端な感度も確認した。

| setup | selected rule | min rank | min pnl | sum pnl | gap | max DD | group loss | EV over max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| hard block | `long:ny_late` | `0.0` | `79.7192` | `370.9706` | `1.8160` | `58.9488` | `252.3560` | `17.5246` |
| extra margin | `long:ny_late:+10/+5` | `0.0` | `79.7192` | `360.6406` | `1.8160` | `58.9488` | `252.3560` | `17.7246` |
| reference | none | `0.5` | `81.5352` | `396.9782` | `0.0000` | `60.0744` | `227.6878` | `16.9756` |

drawdown-onlyなら `long:ny_late` を選ぶが、validation上のmax DD改善は `1.1256` と小さい。その代わり、sum pnlは `-26.0076` から `-36.3376` 悪化し、group lossとEV overestimateも悪化する。これはrisk reductionというより、single metricへの過剰反応に近い。

## 2024-12 Fixed Test

drawdown-onlyで上位になるextra-margin候補を2024-12へ固定適用した。

| candidate | adjusted pnl | raw pnl | trades | PF | DD | forced |
|---|---:|---:|---:|---:|---:|---:|
| prior hybrid top | `-54.6032` | `-18.1410` | `49` | `0.7504` | `97.3520` | `1` |
| hard `long:ny_late`, rank0 | `-15.0538` | `14.6140` | `31` | `0.9154` | `69.6900` | `0` |
| hard `long:ny_late`, rank0.5 | `-5.4938` | `21.2950` | `46` | `0.9658` | `61.1556` | `0` |
| extra margin `long:ny_late:+5`, rank0 | `-15.0538` | `14.6140` | `31` | `0.9154` | `69.6900` | `0` |
| extra margin `long:ny_late:+10`, rank0 | `-15.0538` | `14.6140` | `31` | `0.9154` | `69.6900` | `0` |

extra-margin `+5/+10` は2024-12ではhard block rank0と同じ挙動になった。2024-12は改善するが、NoTrade `0.0` には届かない。

## 判断

- near-top risk selectionの実装は採用する。これは「最高PnLだけを選ぶ」過剰最適化を抑えるための選定インフラとして有用。
- 今回の複合risk設定では `long:ny_late` は選ばれない。validation上、unknown risk reductionを支持するほどのrisk改善がない。
- drawdown-onlyでは `long:ny_late` を選ぶが、これは小さなmax DD差だけに依存し、他のrisk proxyを悪化させるため標準基準にしない。
- `long:ny_late` は引き続き「2024-12 failureを説明する重要regime」だが、標準policyへ昇格しない。

次は、`long:ny_late` をruleで塞ぐよりも、side/regime別のEV calibrationまたはregime-conditioned risk targetとして扱う。validation上でrisk proxyが同時に改善する形にならない限り、単月改善を理由に採用しない。

## Artifacts

- composite hard selection: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_near_top_risk_selection/20260628_122635_model_candidate_selection/`
- composite extra-margin selection: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_near_top_risk_selection/20260628_122635_model_candidate_selection/`
- drawdown-only hard selection: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_near_top_drawdown_only_selection/20260628_122750_model_candidate_selection/`
- drawdown-only extra-margin selection: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_near_top_drawdown_only_selection/20260628_122750_model_candidate_selection/`
- extra-margin fixed 2024-12: `data/reports/backtests/hgb_entry_mlp_exit_long_near_top_extra_margin_2024_12/`
