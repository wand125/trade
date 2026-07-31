# Long Rule Validation Grid

日時: 2026-06-28 21:14 JST
更新日時: 2026-06-28 21:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の `日時` を参照する。

## 目的

前回のposthoc診断で `long:session_regime=ny_late` blockが2024-12損失を大きく縮めた。ただしposthoc採用は避ける必要がある。今回は、`long:ny_late` / `long:range_low_vol` をvalidation gridの候補軸として入れ、2024-12を見ずに再選定できるかを検証する。

## 実装

`model-sweep` に次を追加した。

- `--side-block-rule-sets`
- `--side-extra-margin-rule-sets`

rule setはsemicolon区切り、各set内は既存どおりcomma区切りにした。`none` / `empty` / `-` はno-ruleとして扱う。既存の `--side-block-rules` / `--side-extra-margin-rules` は互換維持する。

また、単一policyの `model-sweep` ではprediction parquetを1回だけ読み、各grid候補で使い回すようにした。preload時は広い列集合を読むだけで、欠損行のdropは候補ごとの必須列で評価直前に行う。これにより、広いread configだけで不要列の欠損に引っ張られることを避け、従来の候補別readと同じ意味を保つ。広いgridではbacktest本体がまだ重いが、parquet読み直しの無駄は避けられる。

## Setup

Input:

- predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- policy: `timed_ev`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`

Local grid:

- entry threshold: `10,15`
- short offset: `4,8`
- side margin: `3,5`
- max predicted hold: `240,480`
- min entry rank: `0,0.5`

Hard block rule sets:

- none
- `long:session_regime=ny_late`
- `long:combined_regime=range_low_vol`
- both

Extra margin rule sets:

- none
- `long:session_regime=ny_late:5`
- `long:session_regime=ny_late:10`
- `long:combined_regime=range_low_vol:5`
- `long:combined_regime=range_low_vol:10`
- both with `5`
- both with `10`

## Validation Selection

Hard block top candidates:

| rank | rule | entry | short offset | side margin | rank filter | max hold | min pnl | sum pnl | min trades | max DD | worst dir/session | EV over max |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | none | `15` | `4` | `5` | `0.5` | `480` | `81.5352` | `396.9782` | `23` | `60.0744` | `-66.9624` | `16.9756` |
| 2 | `long:ny_late` | `15` | `4` | `5` | `0.0` | `480` | `79.7192` | `370.9706` | `17` | `58.9488` | `-66.9624` | `17.5246` |
| 3 | `long:ny_late` | `15` | `4` | `5` | `0.5` | `480` | `78.0572` | `375.5202` | `16` | `60.0744` | `-66.9624` | `17.8068` |
| 4 | `long:range_low_vol` | `15` | `4` | `3` | `0.5` | `480` | `75.7566` | `398.5284` | `36` | `89.3010` | `-89.5794` | `17.6702` |

Extra margin top candidates:

| rank | rule | entry | short offset | side margin | rank filter | max hold | min pnl | sum pnl | min trades | max DD | worst dir/session | EV over max |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | none | `15` | `4` | `5` | `0.5` | `480` | `81.5352` | `396.9782` | `23` | `60.0744` | `-66.9624` | `16.9756` |
| 2 | `long:ny_late:+10` | `15` | `4` | `5` | `0.0` | `480` | `79.7192` | `360.6406` | `17` | `58.9488` | `-66.9624` | `17.7246` |
| 3 | `long:ny_late:+5` | `15` | `4` | `5` | `0.0` | `480` | `79.7192` | `360.6406` | `17` | `58.9488` | `-66.9624` | `17.7246` |
| 4 | `long:ny_late:+10` | `15` | `4` | `5` | `0.5` | `480` | `78.0572` | `365.1372` | `16` | `60.0744` | `-66.9624` | `18.0087` |

Validationの結論は、ruleなしの既存hybrid topが依然として1位。`long:ny_late` は僅差で残るが、sum pnlとEV過大評価は悪化する。`long:range_low_vol` はsum pnlは高い候補もあるが、worst direction/sessionやmax DDが悪く、安定化とは言いにくい。

## 2024-12 Fixed Test

Validationで上位に残った非空rule候補を2024-12へ固定適用した。

| candidate | rule | min rank | side margin | adjusted pnl | raw pnl | trades | PF | DD | forced |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| prior hybrid top | none | `0.5` | `5` | `-54.6032` | `-18.1410` | `49` | `0.7504` | `97.3520` | `1` |
| validation rank2 hard block | `long:ny_late` | `0.0` | `5` | `-15.0538` | `14.6140` | `31` | `0.9154` | `69.6900` | `0` |
| validation rank3 hard block | `long:ny_late` | `0.5` | `5` | `-5.4938` | `21.2950` | `46` | `0.9658` | `61.1556` | `0` |
| range hard block | `long:range_low_vol` | `0.5` | `3` | `-141.5698` | `-87.2740` | `69` | `0.5654` | `154.8342` | `2` |
| range extra margin | `long:range_low_vol:+10` | `0.5` | `3` | `-144.2494` | `-89.5070` | `69` | `0.5608` | `154.8342` | `2` |

`long:ny_late` blockは2024-12で損失を大きく縮めるが、NoTrade `0.0` にはまだ届かない。`long:range_low_vol` 系は2024-12で悪化するため棄却する。

## 判断

- `long:ny_late` blockは「posthocだけの発見」ではなく、validation上でもtop近傍に残ることを確認した。
- ただしvalidation全体topはruleなしであり、`long:ny_late`はsum pnl、side balance、EV overestimateで劣る。
- 2024-12では強く改善するが、それでもNoTrade未満なので標準policyには昇格しない。
- `long:range_low_vol` hard block / extra marginは、2024-12で大きく崩れるため当面捨てる。

次は `long:ny_late` を単体ruleとして採用するのではなく、selection基準に「top min pnlからの許容劣化幅」と「未知月risk reduction」を入れるかを検討する。単月改善のためのblock増加ではなく、validationでtop近傍に残る保守候補をどう選ぶかの問題として扱う。

## Artifacts

- hard block local sweeps: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_local_sweep/`
- hard block selection: `data/reports/backtests/hgb_entry_mlp_exit_long_block_rule_local_selection/20260628_121018_model_candidate_selection/`
- extra margin local sweeps: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_local_sweep/`
- extra margin selection: `data/reports/backtests/hgb_entry_mlp_exit_long_margin_rule_local_selection/20260628_121238_model_candidate_selection/`
- 2024-12 fixed tests: `data/reports/backtests/hgb_entry_mlp_exit_long_rule_validation_candidates_2024_12/`
