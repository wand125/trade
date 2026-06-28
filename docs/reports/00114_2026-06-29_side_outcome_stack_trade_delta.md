# Side Outcome Stack Trade Delta

日時: 2026-06-29 08:27 JST
更新日時: 2026-06-29 08:27 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00113` では `pred_candidate_quality_side_outcome_stack_fixed_*_adjusted_pnl >= 0` gateがvalidationを改善した一方、holdoutの2025-03を `84.0776 -> -5.2898` に壊した。

今回は raw policy と stack gate policy の実取引差分を、`entry_decision_timestamp + direction` で比較する。見る対象は単純なtrade数差ではなく、一玉制約によって消えた取引と新しく入った取引の差。

## 実装

`trade_data.backtest` に `model-trade-delta` を追加した。

主な出力:

- `trade_delta_rows.csv`
- `group_by_month.csv`
- `group_by_month_status.csv`
- `group_by_month_status_direction.csv`
- `group_by_month_status_direction_combined_regime.csv`
- `group_by_month_status_direction_session_regime.csv`
- `group_by_month_status_quality_bucket.csv`

比較区分:

- `common`: raw / candidate の両方に同じ `entry_decision_timestamp + direction` がある
- `only_base`: rawだけにある。candidateでは取引されなかった
- `only_candidate`: candidateだけにある。gate後に新しく入った

`only_base` / `only_candidate` は、一玉制約による経路依存を含む。つまり `only_base` は必ずしも品質gateで直接落ちたとは限らず、candidate側が前の別取引を持っていて入れなかったケースも含む。

実行:

```bash
PYTHONPATH=src python3 -m trade_data.backtest model-trade-delta \
  --base-runs data/reports/backtests/side_outcome_stack_trade_delta_raw_2024_12,data/reports/backtests/side_outcome_stack_trade_delta_raw_2025_03 \
  --candidate-runs data/reports/backtests/side_outcome_stack_trade_delta_stack0_2024_12,data/reports/backtests/side_outcome_stack_trade_delta_stack0_2025_03 \
  --output-dir data/reports/backtests \
  --label side_outcome_stack_trade_delta_compare \
  --top-n 8
```

artifact:

- `data/reports/backtests/20260628_232654_side_outcome_stack_trade_delta_compare/`

## 月別差分

| month | raw trades | stack trades | raw pnl | stack pnl | delta |
|---|---:|---:|---:|---:|---:|
| 2024-12 | `92` | `83` | `-20.8252` | `-18.7302` | `+2.0950` |
| 2025-03 | `152` | `137` | `84.0776` | `-5.2898` | `-89.3674` |

2024-12は、負け取引の除外と新規負け取引の追加がほぼ相殺され、純改善は小さい。

2025-03は、raw側の利益取引を消したうえで、candidate側に新しい損失取引を入れている。

## Status別内訳

| month | status | rows | base pnl | candidate pnl | pnl delta | removed positive | removed negative | added positive | added negative | gate quality mean |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | only_base | `54` | `-67.2954` | `0.0000` | `+67.2954` | `144.5730` | `-211.8684` | `0.0000` | `0.0000` | `-0.4116` |
| 2024-12 | only_candidate | `45` | `0.0000` | `-65.2004` | `-65.2004` | `0.0000` | `0.0000` | `115.4740` | `-180.6744` | `0.7857` |
| 2025-03 | only_base | `77` | `24.5478` | `0.0000` | `-24.5478` | `198.0390` | `-173.4912` | `0.0000` | `0.0000` | `0.4857` |
| 2025-03 | only_candidate | `62` | `0.0000` | `-64.8196` | `-64.8196` | `0.0000` | `0.0000` | `102.0320` | `-166.8516` | `1.3469` |

重要なのは2025-03の `only_base`。平均gate qualityは `0.4857` で、品質予測が必ず低かったわけではない。これは hard gate の直接効果だけではなく、gate後に別取引へ入ったことで後続のraw利益取引に入れなくなる経路依存が大きい。

## Direction / Regime

2025-03の主な悪化:

| group | rows | pnl delta | gate quality mean |
|---|---:|---:|---:|
| only_base long down_low_vol | `12` | `-48.1702` | `-0.3859` |
| only_candidate short range_low_vol | `3` | `-47.9352` | `0.7035` |
| only_base long up_low_vol | `27` | `-25.2298` | `-0.1302` |
| only_candidate long up_low_vol | `27` | `-18.0778` | `0.7288` |

2025-03のdirection別では、`only_base long` が `+73.4000` の利益を持っていた。これを失ったことが最大の悪化要因。`only_base short` は `-48.8522` なので、shortの損失除外効果は出ているが、long利益の逸失とcandidate側の新規損失を補えない。

2024-12は `only_candidate long down_low_vol` が `-65.4130` と悪いが、`only_base long` の除外が `+65.9224` で相殺している。従って2024-12の改善は強いedgeではなく、入れ替えの偶然性が大きい。

## Quality bucket

2025-03の `only_base` は品質bucketで見ると:

| bucket | rows | base pnl | pnl delta |
|---|---:|---:|---:|
| `0-5` | `36` | `51.0784` | `-51.0784` |
| `-10-0` | `41` | `-26.5306` | `+26.5306` |

`0-5` bucketのraw利益取引がcandidateで消えている。これは `min_trade_quality >= 0` を満たす取引でも、一玉制約の経路変化で取り逃がすことを示す。

## Worst examples

2025-03でcandidate側に追加された最大損失:

- `2025-03-31 02:05 UTC`, `short`, `range_low_vol`, `asia`
- candidate adjusted pnl `-39.3240`
- gate quality `1.0360`
- predicted EV `25.6494`
- actual taken best `2.0700`
- EV overestimate vs realized `64.9734`

品質gateを通った取引でも、EV過大評価はまだ大きい。特に「gateを通した新規取引」の実現損失を抑えられていない。

## 判断

`side_outcome_stack_fixed >= 0` の hard gateは標準policyへ採用しない。

理由:

- 2025-03で `-89.3674` の大きなholdout悪化。
- pointwiseな品質予測を hard gateにすると、一玉制約で後続の利益取引を壊す。
- gate通過側の新規取引にも大きなEV過大評価が残る。
- 2024-12の小改善は、負け取引除外と新規負け取引追加の相殺であり、安定したedgeとは言いにくい。

## 次の方針

品質予測は hard gate ではなく、以下へ回す。

- 同時刻・近接候補の優先順位付け
- risk budget別のposition selection
- candidate rankingのtie-break
- `only_candidate` のEV過大評価を抑える診断特徴

次に試す価値があるのは、pointwise entry qualityではなく、stateful policyを意識した「この取引に入ることで後続のより良い取引を逃すか」を扱う教師。候補名としては `blocking_cost`, `replacement_regret`, `stateful_entry_value`。

特に、`only_base 0-5 bucket` の利益逸失を教師に入れない限り、品質gateは低品質除外と同時に良質な後続機会を壊し続ける可能性が高い。

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_backtest`: OK, 67 tests
