# Holding Cap Target Diagnostics

日時: 2026-06-29 18:36 JST
更新日時: 2026-06-29 18:36 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00158` の次課題だった「`range_low_vol` 内でcapすべきshortと保持すべきshortを分ける」ため、holding capの直接効果を教師候補として抽出した。

結論は、`range_low_vol` 全体を除外するより、`range_low_vol:london` と `range_low_vol:rollover` だけcap対象から外すほうが良い診断結果になった。2025-02..2025-08月次独立評価で、risk0は total `404.9366`, min month `-51.3760`, max DD `145.4232`。これはno-context capの `378.8870 / -52.3036 / 145.4232` よりtotal/minが良く、range全除外の `398.2740 / -51.3760 / 181.8916` よりDDが良い。

ただし、このルールは2025-02..2025-08を見た後の診断候補であり、標準採用しない。次の未使用月へ再探索なしで固定確認する。

## Implementation

追加:

- `scripts/experiments/holding_cap_target_diagnostics.py`
  - `model-trade-delta` の `trade_delta_rows.csv` から、capで直接PnLが変わったcommon tradeを抽出する。
  - `cap_value = candidate_adjusted_pnl - base_adjusted_pnl` をdirect target候補にする。
  - `cap_beneficial`, `cap_harmful`, `cap_delta_minutes`, `pred_side_gap` などを付与する。
  - session / EV gap / quality bucket別summaryとwalk-forward prior profileを出す。
- `scripts/experiments/holding_risk_overlay.py`
  - `--include-combined-session-pairs`
  - `--exclude-combined-session-pairs`

これにより `range_low_vol:london,range_low_vol:rollover` のような組み合わせだけcap対象から除外できる。

## Direct Target Diagnostics

入力:

- no-context risk0 delta: `data/reports/backtests/20260629_093003_holding_overlay_no_context_2025_02_08_delta_risk0_month_isolated/`
- no-context risk5 delta: `data/reports/backtests/20260629_093031_holding_overlay_no_context_2025_02_08_delta_risk5_month_isolated/`

`short/range_low_vol` のcommon tradeで、capにより直接holdingが短くなりPnLが変わった例:

| scope | examples | cap value sum | mean | beneficial rate | harmful rate | months |
|---|---:|---:|---:|---:|---:|---:|
| no-context risk0+risk5 | `51` | `14.8088` | `0.2904` | `0.4706` | `0.5294` | `7` |

Session別:

| session | risk0 sum | risk0 support | risk5 sum | risk5 support | note |
|---|---:|---:|---:|---:|---|
| `asia` | `36.8140` | `10` | `37.5940` | `10` | capが有利 |
| `london` | `-24.5522` | `13` | `-21.7518` | `14` | capが不利 |
| `rollover` | `-6.6476` | `2` | `-6.6476` | `2` | capが不利 |

このため、`range_low_vol` を丸ごと除外するのではなく、`london/rollover` だけ除外する候補を検証した。

## Policy Result

2025-02..2025-08、月次独立評価:

| variant | total pnl | min month pnl | max monthly DD | trades | forced |
|---|---:|---:|---:|---:|---:|
| risk0 | `283.8010` | `-66.1420` | `259.0392` | `761` | `3` |
| baseline risk5 | `270.4024` | `-52.9764` | `224.7524` | `726` | `3` |
| no-context cap risk0 | `378.8870` | `-52.3036` | `145.4232` | `825` | `3` |
| no-context cap risk5 | `351.2370` | `-48.5396` | `146.3352` | `790` | `3` |
| exclude all `range_low_vol` risk0 | `398.2740` | `-51.3760` | `181.8916` | `801` | `3` |
| exclude all `range_low_vol` risk5 | `364.8860` | `-43.2404` | `166.9948` | `765` | `3` |
| exclude `range_low_vol:london,rollover` risk0 | `404.9366` | `-51.3760` | `145.4232` | `810` | `3` |
| exclude `range_low_vol:london,rollover` risk5 | `360.9802` | `-43.2404` | `146.3352` | `774` | `3` |

月別:

| month | no-context risk0 | exclude all range risk0 | exclude london/rollover risk0 |
|---|---:|---:|---:|
| 2025-02 | `114.5970` | `134.1962` | `127.4056` |
| 2025-03 | `39.5598` | `65.6888` | `54.0314` |
| 2025-04 | `82.7800` | `47.7880` | `85.0760` |
| 2025-05 | `-52.3036` | `-51.3760` | `-51.3760` |
| 2025-06 | `129.4450` | `135.7412` | `130.1558` |
| 2025-07 | `-0.8914` | `-6.1894` | `-6.0564` |
| 2025-08 | `65.7002` | `72.4252` | `65.7002` |

`exclude london/rollover` は2025-04のDD悪化を避けつつ、no-contextよりtotalを上げた。ただし2025-08単月では `exclude all range` に負ける。

## Residual Target After Pair Exclusion

ペア除外後に残った `short/range_low_vol` direct target:

| examples | cap value sum | mean | beneficial rate | harmful rate | months |
|---:|---:|---:|---:|---:|---:|
| `20` | `74.4080` | `3.7204` | `0.6500` | `0.3500` | `5` |

残ったtargetは改善したが、supportは少ない。深層学習targetとしてはまだ小さすぎるため、単体モデル化よりも、exit/holding targetの補助ラベルとして扱う。

## Judgment

- `range_low_vol:london/rollover` 除外は、現在の診断セットでは最もバランスが良いholding cap候補。
- ただし、session別判断は2025-02..2025-08を見た後のpost-hocルールである。標準採用しない。
- direct cap targetは51件しかなく、深層学習の直接教師としては不足。より広い「holding短縮が有利か」という教師をprediction全行から作る必要がある。
- 次は、未使用月にこのペア除外候補を固定適用するか、またはdataset生成側に `cap60_vs_event_holding_delta` のようなdense targetを追加する。

## Artifacts

- direct target diagnostics no-context: `data/reports/backtests/20260629_093252_holding_cap_target_range_low_vol_short_2025_02_08/`
- pair exclusion policy: `data/reports/backtests/20260629_093356_holding_risk_overlay_short_only_excl_range_london_rollover_2025_02_08_month_isolated/`
- pair exclusion deltas risk0/risk5:
  - `data/reports/backtests/20260629_093511_holding_overlay_excl_range_london_rollover_2025_02_08_delta_risk0_month_isolated/`
  - `data/reports/backtests/20260629_093541_holding_overlay_excl_range_london_rollover_2025_02_08_delta_risk5_month_isolated/`
- residual target diagnostics: `data/reports/backtests/20260629_093552_holding_cap_target_range_low_vol_short_excl_london_rollover_2025_02_08/`
