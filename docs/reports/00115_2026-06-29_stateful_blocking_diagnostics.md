# Stateful Blocking Diagnostics

日時: 2026-06-29 08:35 JST
更新日時: 2026-06-29 08:35 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00114` で、pointwiseな `side_outcome_stack_fixed >= 0` gateは一玉制約の経路依存を壊すことが分かった。

今回は、candidate policyの取引が保有中にbase policyのどの取引機会をブロックしたかを明示的に測る。

この診断は次の教師候補である `blocking_cost`, `replacement_regret`, `stateful_entry_value` の前段。

## 実装

`model-trade-delta` に以下を追加した。

- `blocking_pairs.csv`
- `group_by_blocking_candidate_month_status_direction.csv`
- `group_by_blocking_candidate_month_status_direction_combined_regime.csv`
- `group_by_blocking_candidate_month_status_direction_session_regime.csv`

定義:

- candidate取引の区間: `entry_decision_timestamp < base_only.entry_decision_timestamp <= candidate_exit_decision_timestamp`
- `blocked_base_adjusted_pnl`: candidate保有中に入れなかったbase-only取引のPnL合計
- `blocked_base_positive_pnl`: そのうち正のPnL合計
- `candidate_stateful_net_adjusted_pnl`: `candidate_adjusted_pnl - blocked_base_adjusted_pnl`
- `candidate_stateful_positive_cost_adjusted_pnl`: `candidate_adjusted_pnl - blocked_base_positive_pnl`

`candidate_stateful_net_adjusted_pnl` は、candidateがbase側の負け取引を避けた効果も含める。`candidate_stateful_positive_cost_adjusted_pnl` は、失った勝ち機会だけを機会費用として見る。

実行:

```bash
PYTHONPATH=src python3 -m trade_data.backtest model-trade-delta \
  --base-runs data/reports/backtests/side_outcome_stack_trade_delta_raw_2024_12,data/reports/backtests/side_outcome_stack_trade_delta_raw_2025_03 \
  --candidate-runs data/reports/backtests/side_outcome_stack_trade_delta_stack0_2024_12,data/reports/backtests/side_outcome_stack_trade_delta_stack0_2025_03 \
  --output-dir data/reports/backtests \
  --label side_outcome_stack_trade_delta_blocking \
  --top-n 8
```

artifact:

- `data/reports/backtests/20260628_233539_side_outcome_stack_trade_delta_blocking/`

## Direction別結果

| month | status | direction | candidate pnl | blocked base count | blocked base pnl | blocked positive | blocked negative | stateful net | positive-cost stateful |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | only_candidate | long | `-72.3252` | `14` | `-67.0976` | `22.3300` | `-89.4276` | `-5.2276` | `-94.6552` |
| 2024-12 | only_candidate | short | `7.1248` | `9` | `-0.7790` | `7.7650` | `-8.5440` | `7.9038` | `-0.6402` |
| 2025-03 | only_candidate | long | `-18.8318` | `18` | `51.0776` | `78.2900` | `-27.2124` | `-69.9094` | `-97.1218` |
| 2025-03 | only_candidate | short | `-45.9878` | `25` | `7.1968` | `24.7060` | `-17.5092` | `-53.1846` | `-70.6938` |

2025-03は、candidate側で新しく入ったlong/shortの両方がstatefulにも悪い。特にlongは自身の損失 `-18.8318` に加え、base側の純利益 `+51.0776` を失っている。

2024-12のonly_candidate longは、candidate自身は `-72.3252` と悪いが、同時にbase側の負け取引 `-89.4276` も避けているため、netでは `-5.2276` まで緩む。一方、positive-costで見ると `-94.6552` で、勝ち機会を失うリスクは大きい。

## Regime別の主な悪化

| month | status | direction | combined regime | candidate pnl | blocked base pnl | blocked positive | stateful net | gate quality mean |
|---|---|---|---|---:|---:|---:|---:|---:|
| 2025-03 | only_candidate | long | up_low_vol | `-18.0778` | `38.3476` | `65.5600` | `-56.4254` | `0.7288` |
| 2025-03 | only_candidate | short | range_low_vol | `-47.9352` | `0.0000` | `0.0000` | `-47.9352` | `0.7035` |
| 2025-03 | only_candidate | long | down_low_vol | `-0.7540` | `12.7300` | `12.7300` | `-13.4840` | `0.6505` |
| 2025-03 | only_candidate | short | up_normal_vol | `-6.1846` | `-0.7172` | `16.2160` | `-5.4674` | `2.1121` |

品質予測meanはすべて正。つまり、pointwise qualityは「この取引自体がよさそうか」は見ているが、「保有中に何を逃すか」は見ていない。

## Worst pair

最悪pair:

- month: `2025-03`
- candidate: `only_candidate long up_low_vol`
- candidate adjusted pnl: `-6.9720`
- blocked base: `long down_low_vol`
- blocked base adjusted pnl: `19.7500`
- pair stateful net: `-26.7220`
- candidate gate quality: `0.6650`

この例は、品質gateを通った取引が小さな予測優位で入った結果、より大きい後続long機会をブロックしている。

## 判断

次の研究の中心は、個別候補の実現PnLではなく、保有による機会費用を含むstateful教師に移す。

候補target:

- `blocking_cost = max(blocked_base_adjusted_pnl, 0)`
- `positive_blocking_cost = blocked_base_positive_pnl`
- `replacement_regret = blocked_base_adjusted_pnl - candidate_adjusted_pnl`
- `stateful_entry_value = candidate_adjusted_pnl - blocked_base_adjusted_pnl`
- `stateful_positive_cost_value = candidate_adjusted_pnl - blocked_base_positive_pnl`

最初の実装候補は `stateful_entry_value` と `stateful_positive_cost_value`。前者は負け取引を避けた効果も評価し、後者は勝ち機会の取り逃しを強く罰する。

ただし注意点:

- この教師はbase policyとの差分に依存するため、base policyを固定したうえで作る。
- OOF/walk-forwardで作らないと、後付けのpath情報がリークする。
- 直接hard gateにせず、ranking/tie-breakまたはEV補正として検証する。

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_backtest.BacktestTests.test_model_trade_delta_compares_added_and_removed_trades_with_gate_quality`: OK
