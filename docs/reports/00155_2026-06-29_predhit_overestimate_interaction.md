# Predhit Overestimate Interaction

日時: 2026-06-29 17:28 JST
更新日時: 2026-06-29 17:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00145` の `pred_hit_actual_miss` 単独risk、`00152` の high-overestimate q75 単独risk、`00154` のstateful candidate riskはいずれも、直接penaltyでは標準policyを上回らなかった。

今回は単独riskを増やすのではなく、profit-barrier過信とEV過大評価が同時に強い局面だけを小さく補正する。

- `pred_hit_actual_miss_prob * ev_overestimate_high_prob`
- `pred_hit_actual_miss_prob * q75_high_overestimate_prob`

## 実装

`scripts/experiments/predhit_overestimate_interaction.py` を追加した。

このscriptは以下を一括で行う。

1. chronological q75 high-overestimate OOF predictionと2025-05 apply predictionを結合する。
2. side別interaction risk列を作る。
3. 既存 `stateful floor risk` に `weight / 5 * interaction_risk` を足す。
4. `model-policy` と同じ標準条件で2025-02..2025-05を月別評価する。
5. 月別metrics、summary、manifest、個別tradesを保存する。

注意点: 初回実装では評価月の `dataset_month` だけへpredictionを絞っていたため、post期間のシグナルが標準CLIと一致しなかった。修正後は `model-policy` CLIと同じく、統合prediction frame全体を各月評価へ渡している。この修正後のrunだけを判断に使う。

## Data

- validation OOF: `experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/predictions_validation_oof_trade_overestimate_high_model.parquet`
- 2025-05 apply: `experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/predictions_apply_trade_overestimate_high_model.parquet`
- months: `2025-02,2025-03,2025-04,2025-05`
- cost: `profit_multiplier=1.0`, `loss_multiplier=1.2`, spread `0.2`, slippage `0.1`, execution delay `1`
- policy: `timed_ev`, entry `12`, short offset `6`, side margin `5`, MLP holding guard `30..480m`, `risk_penalty=5`

## Risk Scale

interactionは確率同士の積なので、`evhigh` はかなり小さく、`q75` はshort側で発火幅が大きい。

| column | side | mean risk | p90 risk | max risk |
|---|---:|---:|---:|---:|
| `predhit_evhigh` | long | `0.000424` | `0.000467` | `0.070895` |
| `predhit_evhigh` | short | `0.001554` | `0.004517` | `0.053161` |
| `predhit_q75` | long | `0.006106` | `0.006692` | `0.147592` |
| `predhit_q75` | short | `0.029955` | `0.116647` | `0.206946` |

## Coarse Grid

| label | total PnL | min month | max DD | trades |
|---|---:|---:|---:|---:|
| risk0 | `101.5974` | `-61.3708` | `259.0392` | 408 |
| baseline risk5 | `91.9002` | `-48.2052` | `224.7524` | 386 |
| predhit evhigh w5 | `92.2242` | `-47.8812` | `224.7524` | 386 |
| predhit evhigh w10 | `91.6372` | `-46.0048` | `224.7524` | 387 |
| predhit q75 w1 | `94.9368` | `-47.8812` | `224.7524` | 387 |
| predhit q75 w2 | `83.7568` | `-47.8812` | `224.7524` | 386 |
| predhit q75 w5 | `97.4686` | `-27.2324` | `243.2924` | 386 |
| predhit q75 w10 | `65.3420` | `-44.7132` | `250.7284` | 385 |

`evhigh` interactionは小さすぎ、ほぼbaselineと同じ。`q75` interactionは防御効果が出るが、weightに敏感。

## Fine Grid

| label | total PnL | min month | max DD | trades |
|---|---:|---:|---:|---:|
| predhit q75 w4 | `107.2486` | `-22.9762` | `233.5124` | 386 |
| risk0 | `101.5974` | `-61.3708` | `259.0392` | 408 |
| predhit q75 w6 | `101.4240` | `-27.2324` | `243.2924` | 386 |
| predhit q75 w7 | `98.3746` | `-30.1732` | `243.2924` | 384 |
| predhit q75 w5 | `97.4686` | `-27.2324` | `243.2924` | 386 |
| baseline risk5 | `91.9002` | `-48.2052` | `224.7524` | 386 |
| predhit q75 w3 | `80.5836` | `-43.8988` | `233.5124` | 385 |
| predhit q75 w8 | `62.9580` | `-47.8032` | `248.8924` | 385 |

月別:

| label | 2025-02 | 2025-03 | 2025-04 | 2025-05 |
|---|---:|---:|---:|---:|
| risk0 | `141.4436` | `60.2172` | `-38.6926` | `-61.3708` |
| baseline risk5 | `113.1642` | `27.1660` | `-0.2248` | `-48.2052` |
| predhit q75 w3 | `114.7686` | `25.6986` | `-15.9848` | `-43.8988` |
| predhit q75 w4 | `114.7686` | `32.9086` | `-17.4524` | `-22.9762` |
| predhit q75 w5 | `114.7686` | `32.9086` | `-27.2324` | `-22.9762` |
| predhit q75 w6 | `117.6670` | `32.9086` | `-27.2324` | `-21.9192` |
| predhit q75 w7 | `118.8674` | `36.3682` | `-26.6878` | `-30.1732` |
| predhit q75 w8 | `118.8674` | `27.1716` | `-35.2778` | `-47.8032` |

## Delta Diagnosis

`predhit_q75_w4` は4ヶ月合計でrisk0も上回るが、weight周辺の安定した台地ではない。

2025-05ではbaseline risk5 `-48.2052` から `-22.9762` へ改善。主因はcommon `long/down_low_vol` 10 tradesの損失が `-117.9480 -> -94.0680` へ縮んだこと。これは単純な悪いentry削除ではなく、同じentry群のexit/holding経路が変わった改善。

2025-04ではbaseline `-0.2248` から `-17.4524` へ悪化。`only_base long/down_high_vol +8.7600` と `only_base short/range_normal_vol +7.0000` を落とし、`only_candidate long/up_low_vol -1.4676` を追加したことが主因。

## 判断

1. `predhit_q75_w4` は2025-02..2025-05で total `107.2486`, min month `-22.9762` となり、今回の固定4ヶ月ではrisk0/risk5を上回った。
2. ただし `w3 -> 80.5836`, `w4 -> 107.2486`, `w5 -> 97.4686` とweight感度が大きい。安定した台地ではないため標準採用しない。
3. `predhit_evhigh` interactionはrisk scaleが小さく、baselineからほぼ動かない。単独では優先度を下げる。
4. `predhit_q75` interactionは、防御候補として残す。次は2025-06以降または別walk-forward foldへ固定適用し、weightを再探索せず `w4` / `w6` を事前登録で確認する。
5. 今回の前進は「過大評価probを単独penaltyにしない」「profit-barrier過信とのinteractionで狭く使う」方向が、少なくとも一部月でexit/holding損失を縮める可能性を示した点。

## Artifacts

- script: `scripts/experiments/predhit_overestimate_interaction.py`
- coarse run: `data/reports/modeling/20260629_082447_predhit_overestimate_interaction_2025_02_05/`
- fine run: `data/reports/modeling/20260629_082659_predhit_overestimate_interaction_fine_2025_02_05/`
- fine backtests: `data/reports/backtests/20260629_082659_predhit_overestimate_interaction_fine_2025_02_05/`
- w4 delta 2025-04: `data/reports/backtests/20260629_082804_predhit_q75_w4_delta_2025_04/`
- w4 delta 2025-05: `data/reports/backtests/20260629_082804_predhit_q75_w4_delta_2025_05/`

## 検証

- `python3 -m py_compile scripts/experiments/predhit_overestimate_interaction.py`: pass
- `python3 scripts/experiments/predhit_overestimate_interaction.py`: pass
- `python3 scripts/experiments/predhit_overestimate_interaction.py --weights 3,4,5,6,7,8 --label predhit_overestimate_interaction_fine_2025_02_05`: pass
- `python3 -m trade_data.backtest model-trade-delta`: pass, 4 runs

## 次の作業

1. `predhit_q75_w4` / `w6` を固定候補として、未使用月または別walk-forward splitへ再探索なしで適用する。
2. 2025-04の悪化原因である良いbase trade削除を抑えるため、riskをentry score全体ではなくexit/holding補正へ寄せる。
3. q75 probabilityをそのままriskにするのではなく、session/regime別のcalibrationとsupport floorを入れる。
