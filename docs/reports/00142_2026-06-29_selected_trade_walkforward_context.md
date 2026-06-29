# Selected Trade Walk-Forward Context

日時: 2026-06-29 13:16 JST
更新日時: 2026-06-29 13:16 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00141` で `mean_match + session_floor_lowered risk=5` は2025-05 highcostを改善したが、まだNoTrade未満だった。trade deltaでは改善が少数の入れ替えに依存し、common trade側に `long:down_low_vol` と `short:up_normal_vol` の大きな損失が残った。

今回は、候補差分ではなく実際に選択されたtradeを対象に、対象月より前の月だけで文脈riskを付与する診断を追加した。

## 実装

`model-trade-context-walkforward-stress` を追加した。

- 入力: model-policy run親ディレクトリ、または `trades.csv`
- 出力: `selected_trades.csv`, `walkforward_selected_trades.csv`, `walkforward_profile_drift.csv`, `walkforward_month_summary.csv`, `walkforward_context_outcomes.csv`, `summary.json`
- target: default `adjusted_pnl`
- default group: `direction,combined_regime`
- leak control: target month自身はprofileに使わず、過去月だけを使う

既存の validation-positive / holdout-negative stress に加えて、全過去月の文脈平均を使う列も追加した。

- `walkforward_prior_context_target_mean`
- `walkforward_prior_context_loss_flag`
- `target_walkforward_prior_context_mean_floor`

これは、反転ではなく「過去から一貫して弱い文脈」を拾うためのもの。たとえば直近holdout supportが0でも、全過去supportが十分あり平均が負ならfuture-safeに弱い文脈として扱える。

また、docs運用について、レポート順序はOSの更新時刻ではなく本文の `日時` を使うことをテストで明示した。`tests/test_docs_reports.py` に、filesystem mtimeを逆順にしても内部 `日時` で並ぶ検証を追加した。

## 固定run生成

`00140` / `00141` と同じ固定条件で、`risk=5` の7ヶ月分model-policy tradesを生成した。

| cost | months | total PnL | min month | trades |
|---|---|---:|---:|---:|
| base | 2024-11..2025-05 | `567.7900` | `8.0868` | 603 |
| highcost | 2024-11..2025-05 | `354.8408` | `-52.9764` | 607 |

2025-05を含めると、highcostの未解決損失がそのまま残る。

## 2025-05 Context

`direction + combined_regime`、supportは validation `20`, holdout `3`, all-prior `20`。

| cost | context | trades | PnL | stress flags | prior support | prior mean | prior loss |
|---|---|---:|---:|---:|---:|---:|---|
| base | `long:down_low_vol` | 10 | `-109.4924` | 10 | 81 | `+0.7213` | false |
| base | `short:up_normal_vol` | 30 | `-72.0210` | 30 | 49 | `+0.6628` | false |
| highcost | `long:down_low_vol` | 10 | `-117.9480` | 10 | 81 | `+0.5263` | false |
| highcost | `short:up_normal_vol` | 30 | `-100.9936` | 30 | 49 | `-0.0692` | true |

広い文脈では、両方とも過去月だけのstressで捕捉できる。`short:up_normal_vol` はhighcostのall-prior平均も負になっており、EV過大評価の補正targetとして使いやすい。

## Session Split

`direction + combined_regime + session_regime`、supportは validation `10`, holdout `3`, all-prior `10`。

| cost | context | trades | PnL | stress flags | prior support | prior mean | prior loss |
|---|---|---:|---:|---:|---:|---:|---|
| base | `long:down_low_vol:london` | 3 | `-84.9120` | 0 | 11 | `-8.4318` | true |
| base | `short:up_normal_vol:asia` | 13 | `-38.6720` | 0 | 15 | `-2.8510` | true |
| base | `short:up_normal_vol:london` | 8 | `-56.6990` | 0 | 26 | `+2.6089` | false |
| highcost | `long:down_low_vol:london` | 3 | `-87.6396` | 0 | 11 | `-9.2242` | true |
| highcost | `short:up_normal_vol:asia` | 13 | `-56.7420` | 0 | 15 | `-3.3029` | true |
| highcost | `short:up_normal_vol:london` | 8 | `-54.5500` | 0 | 26 | `+1.8360` | false |

session分解では `long:down_low_vol:london` が特に重要。これは直近holdout supportが0なのでflip stressでは拾えないが、all-prior mean floorでは拾える。

`short:up_normal_vol:london` は2025-05で大きく負けたが、過去平均は正なので単純な文脈riskとしては捕捉しにくい。これはexit timing / EV calibration / higher-order feature側に戻すべき失敗。

## 判断

今回の追加は有効。`00141` のcommon trade損失は、少なくとも以下の2系統に分けられる。

1. 過去月だけで反転stressとして見えていたもの: `short:up_normal_vol`, `long:down_low_vol`
2. 反転ではないが、全過去平均で弱いもの: `long:down_low_vol:london`, `short:up_normal_vol:asia`

ただし、これをhard blockにはしない。supportが細いsession文脈もあり、hard blockはNoTrade化や経路依存の副作用を起こす。次は `target_walkforward_context_stress_adjusted` と `target_walkforward_prior_context_mean_floor` を、downside分類・EV校正・ranking featureへ戻す。

## Artifacts

- fixed policy runs: `data/reports/backtests/20260629_selected_trade_context_wf/`
- base prior context: `data/reports/backtests/20260629_041537_selected_trade_wf_base_risk5_prior/`
- highcost prior context: `data/reports/backtests/20260629_041537_selected_trade_wf_highcost_risk5_prior/`
- base session prior context: `data/reports/backtests/20260629_041537_selected_trade_wf_base_risk5_session_prior/`
- highcost session prior context: `data/reports/backtests/20260629_041537_selected_trade_wf_highcost_risk5_session_prior/`

## 検証

- `python3 -m unittest tests.test_docs_reports tests.test_backtest`: OK, 81 tests
- `python3 -m trade_data.backtest model-trade-context-walkforward-stress --help`: OK
- `python3 -m trade_data.backtest stateful-examples-walkforward-stress --help`: OK

## 次の作業

1. `target_walkforward_prior_context_mean_floor` をstateful downside/ranking用targetへ入れ、既存 `walkforward_floor_lowered` と比較する。
2. `short:up_normal_vol:london` のように過去contextだけで捕捉できない損失は、exit timing target、EV overestimate、side confidence、session時間帯の相互作用で診断する。
3. 2025-05上でhard blockや閾値最適化はしない。次は教師・校正targetを作って、chronological OOFと別月で評価する。
