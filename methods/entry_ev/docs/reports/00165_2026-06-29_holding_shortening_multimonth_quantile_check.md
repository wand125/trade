# Holding Shortening Multimonth Quantile Check

日時: 2026-06-29 20:06 JST
更新日時: 2026-06-29 20:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00164` では2025-04単月validの経験CDFでholding-shortening probabilityをquantile化した。今回は、2025-02..2025-04の3ヶ月をまとめたvalidation分布でquantile列を作り、3ヶ月validationでthreshold/capを選んでから2025-05へ固定適用した。

結論:

- 3ヶ月validationのquantile最良は `threshold=0.75`, `cap=60`。
- validation合計は disabled `-172.4522` に対して `-75.2444` まで改善した。
- ただしraw threshold版のvalidation最良 `0.60 / 60` は `-53.9566` で、quantile版はこれを超えない。
- 2025-05へ固定適用すると、quantile `0.75 / 60` は `-186.1276` で disabled `-179.2516` より悪化した。
- 2025-05のshort-side multimonth quantileは `>=0.75` が464行しかなく、validation OOF分布とchronological apply分布のズレがまだ残る。

よって、holding-shorteningの単純cap発火は継続候補から降格する。quantile化の実装は残すが、threshold/capを直接policyにするのではなく、entry quality / exit risk modelのfeatureとして使う方向へ戻す。

## Data

Validation fit distribution:

- `data/reports/modeling/20260629_holding_shortening_policy_hook_multimonth/predictions_2025_02_merged.parquet`
- `data/reports/modeling/20260629_holding_shortening_policy_hook_multimonth/predictions_2025_03_merged.parquet`
- `data/reports/modeling/20260629_holding_shortening_policy_hook_multimonth/predictions_2025_04_merged.parquet`

Combined fit output:

- `data/reports/modeling/20260629_holding_shortening_quantile_multimonth_validation/predictions_2025_02_04_combined_fit.parquet`

Quantile outputs:

- `data/reports/modeling/20260629_holding_shortening_quantile_multimonth_validation/predictions_2025_02_quantile.parquet`
- `data/reports/modeling/20260629_holding_shortening_quantile_multimonth_validation/predictions_2025_03_quantile.parquet`
- `data/reports/modeling/20260629_holding_shortening_quantile_multimonth_validation/predictions_2025_04_quantile.parquet`
- `data/reports/modeling/20260629_holding_shortening_quantile_multimonth_validation/predictions_2025_05_quantile.parquet`

## Validation Aggregate

Conditions:

- months: `2025-02`, `2025-03`, `2025-04`
- policy: `timed_ev`
- `entry_threshold=10`
- `side_margin=5`
- `risk_penalty=0`
- `profit_multiplier=1.0`
- `loss_multiplier=1.20`
- quantile thresholds: `inf,0.0,0.05,0.1,0.25,0.5,0.75,0.9`
- caps: `30,60,120`

Top aggregate candidates:

| quantile threshold | cap | sum pnl | mean pnl | min pnl | max DD | mean trades |
|---:|---:|---:|---:|---:|---:|---:|
| `0.75` | `60` | `-75.2444` | `-25.0815` | `-60.0834` | `465.0004` | `63.3333` |
| `0.75` | `120` | `-113.6566` | `-37.8855` | `-119.0180` | `506.7924` | `54.6667` |
| `0.90` | `120` | `-130.3526` | `-43.4509` | `-115.9670` | `527.9464` | `47.3333` |
| `0.75` | `30` | `-131.0358` | `-43.6786` | `-114.7792` | `491.2324` | `74.3333` |
| `0.25` | `120` | `-141.1698` | `-47.0566` | `-85.2064` | `409.0248` | `87.3333` |
| `inf` | `60` | `-172.4522` | `-57.4841` | `-125.9826` | `533.9704` | `43.0000` |

Raw threshold版の3ヶ月validation最良は `0.60 / 60` の `-53.9566`。quantile版はdisabledより改善するが、raw版のbestを超えない。

Selected monthly comparison:

| month | disabled | raw `0.60 / 60` | multimonth quantile `0.75 / 60` |
|---|---:|---:|---:|
| 2025-02 | `-53.5244` | `-43.7620` | `-60.0834` |
| 2025-03 | `7.0548` | `32.6068` | `36.6012` |
| 2025-04 | `-125.9826` | `-42.8014` | `-51.7622` |
| total | `-172.4522` | `-53.9566` | `-75.2444` |

quantile `0.75 / 60` は2025-03ではrawより良いが、2025-02で悪化し、総合ではrawに負ける。

## Fixed 2025-05

2025-02..04 validationで選んだ `0.75 / 60` を、2025-05へ再探索なしで固定適用した。

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | avg holding min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| disabled | `-179.2516` | `-43.8680` | `56` | `0.5179` | `0.7793` | `269.5060` | `1` | `539.1071` |
| raw valid-calibrated `0.50 / 60` | `-79.7894` | `47.0650` | `119` | `0.4622` | `0.8952` | `212.4794` | `1` | `231.5630` |
| single-month quantile `0.25 / 60` | `-89.7428` | `46.3150` | `127` | `0.4646` | `0.8901` | `222.6048` | `1` | `215.2126` |
| multimonth quantile `0.75 / 60` | `-186.1276` | `-50.8780` | `56` | `0.5179` | `0.7706` | `276.3820` | `1` | `538.0714` |

2025-05の同一gridをpost-hocで見るとbestは `0.25 / 60` の `-102.4924` だが、これはvalidation選定値ではない。validation最良 `0.75 / 60` は発火が少なく、わずかに悪いcapだけが効いてdisabledより下がった。

2025-05 multimonth quantile activation:

| side | rows `>=0.75` | rows `>=0.25` | p90 | max |
|---|---:|---:|---:|---:|
| long quantile | `4,598` | `28,690` | `0.8156` | `1.0000` |
| short quantile | `464` | `22,023` | `0.6233` | `0.8456` |

short側のhigh-quantile発火が薄い。validation OOF分布で作った相対順位をchronological apply modelへ持ち込むと、特にshort側のスケールがずれている。

## Delta

2025-05 disabled vs multimonth quantile `0.75 / 60`:

| base trades | candidate trades | base pnl | candidate pnl | delta |
|---:|---:|---:|---:|---:|
| `56` | `56` | `-179.2516` | `-186.1276` | `-6.8760` |

大きなtrade set変更ではなく、common long/range_normal_volの一部cap悪化とonly-candidate short/up_low_volの小損失で負けている。entry改善ではなく保有時間変更だけが薄く悪く出た。

## Judgment

multimonth quantile化は、3ヶ月validationではdisabledを上回る。しかし、raw threshold版を超えず、2025-05固定ではdisabledより悪化した。したがって、holding-shortening probabilityを直接cap発火に使う方向は本流から外す。

重要な学び:

- quantile化しても、OOF validation modelとchronological apply modelの分布差は残る。
- threshold/cap最適化は月・fit方式に強く依存する。
- 保有時間だけを短縮しても、entry qualityやside/regimeの悪い追加tradeを解けない。

次は、holding-shortening probabilityを直接売買ルールにせず、selected trade outcome / exit regret / overestimate risk の補助featureとして使う。特に、発火ルールではなく「長く持つ予測の信用度を下げる」「exit timing modelの校正特徴に入れる」方向を優先する。

## Verification

- combined validation fit parquet creation: OK
- quantile column generation for 2025-02..05: OK
- 2025-02..04 quantile sweeps: OK
- 2025-05 fixed quantile policy and sweep: OK
- 2025-05 delta diagnosis: OK
- `python3 -m unittest tests.test_docs_reports`: OK, 3 tests
