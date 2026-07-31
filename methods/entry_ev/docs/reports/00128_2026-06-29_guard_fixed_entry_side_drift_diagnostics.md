# Guard Fixed Entry Side Drift Diagnostics

日時: 2026-06-29 10:33 JST
更新日時: 2026-06-29 10:33 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00127` では、guard固定後のvalidation top候補がapply 4ヶ月へ外挿しないことを確認した。

今回は同じ固定候補について、月別PnLだけでなく、選択tradeの露出、標準候補との差分、stateful blocking targetを確認し、なぜvalidation topが壊れたかを診断する。

## 条件

比較対象:

- 現行標準: `entry=12`, short offset `6`, side margin `5`, short penalty `down_low_vol:5`, `up_low_vol:10`
- validation top: `entry=14`, short offset `4`, side margin `5`, short penalty `down_low_vol:5`, `up_low_vol:10`, `range_low_vol:5`

共通:

- policy: `timed_ev`
- loss multiplier: `1.20`
- MLP holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- MLP holding guard: CLI auto default, resolved `min_valid_predicted_hold_minutes=30`
- max predicted hold: `480`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- apply months: `2024-12`, `2025-02`, `2025-03`, `2025-04`
- cost cases: base and high cost (`spread=0.2`, `slippage=0.1`, `execution_delay=1`)

## Split Summary

| split | cost | standard PnL | top PnL | top-standard | standard trades | top trades | min month standard | min month top |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| validation | base | `622.6486` | `685.5456` | `+62.8970` | `275` | `228` | `138.0338` | `154.4590` |
| validation | high cost | `500.5422` | `586.9640` | `+86.4218` | `275` | `228` | `96.8776` | `138.6648` |
| apply | base | `246.8762` | `-42.4328` | `-289.3090` | `377` | `306` | `-18.7168` | `-50.1562` |
| apply | high cost | `132.6970` | `-157.7340` | `-290.4310` | `380` | `308` | `-34.3748` | `-69.2394` |

validationではtopが取引数を47件減らして成績を上げた。一方applyでは取引数を71-72件減らした結果、合計PnLが約 `-290` 悪化した。

## Trade Delta

`model-trade-delta` で、標準候補とtop候補のtradeを `common`, `only_base`, `only_candidate` に分解した。

| split | cost | status | base PnL | top PnL | delta |
|---|---|---|---:|---:|---:|
| validation | base | common | `293.9988` | `326.0672` | `+32.0684` |
| validation | base | only_base | `328.6498` | `0.0000` | `-328.6498` |
| validation | base | only_candidate | `0.0000` | `359.4784` | `+359.4784` |
| apply | base | common | `-15.0466` | `-62.0386` | `-46.9920` |
| apply | base | only_base | `261.9228` | `0.0000` | `-261.9228` |
| apply | base | only_candidate | `0.0000` | `19.6058` | `+19.6058` |
| validation | high cost | common | `268.0430` | `301.3136` | `+33.2706` |
| validation | high cost | only_base | `232.4992` | `0.0000` | `-232.4992` |
| validation | high cost | only_candidate | `0.0000` | `285.6504` | `+285.6504` |
| apply | high cost | common | `-71.4596` | `-131.0640` | `-59.6044` |
| apply | high cost | only_base | `204.1566` | `0.0000` | `-204.1566` |
| apply | high cost | only_candidate | `0.0000` | `-26.6700` | `-26.6700` |

validationでは、top専用tradeが標準専用tradeの喪失を上回った。しかしapplyでは、標準専用tradeの利益を大きく失い、top専用tradeはbaseでわずかにプラス、高コストではマイナスになった。さらにcommon tradeのexit/pathも悪化した。

## Stateful Target Drift

top候補側のstateful candidate target平均は、validationでは全月プラスだったが、applyでは3/4ヶ月でマイナスになった。

| split | cost | month | target mean | target sum | blocking cost |
|---|---|---|---:|---:|---:|
| validation | base | `2024-07` | `1.8330` | `95.3184` | `172.4770` |
| validation | base | `2024-09` | `1.7054` | `85.2696` | `218.1374` |
| validation | base | `2024-11` | `2.8303` | `189.6290` | `103.4760` |
| validation | base | `2025-01` | `1.9971` | `117.8294` | `168.0530` |
| apply | base | `2024-12` | `0.9839` | `61.9878` | `115.5940` |
| apply | base | `2025-02` | `-1.7983` | `-147.4614` | `269.1262` |
| apply | base | `2025-03` | `-0.1697` | `-15.6120` | `206.6466` |
| apply | base | `2025-04` | `-2.1726` | `-149.9120` | `131.4910` |

特に2025-02では、top専用 `long:up_low_vol` がbaseで `-42.9714` を出し、同時に標準側の `+101.6036` をブロックしたため、stateful netは `-144.5750` になった。これはpointwiseなentry/side評価では見えにくい、一玉制約下の機会損失である。

## 判断

validation top候補は採用しない。

理由:

- validation上の改善は、標準専用tradeを捨ててtop専用tradeへ置換したことによるが、その置換はapplyで再現しない。
- top候補のstateful targetはvalidationで全月プラス、applyで3/4ヶ月マイナスになり、regime driftが明確。
- high costでも同じ方向に崩れ、取引コストへの耐性がない。
- MLP holding guardは高回転破綻を止めるが、entry/side gridの外挿問題は解決していない。

したがって、entry threshold / short offset / side penalty の探索をさらに増やすのは本流にしない。次は、候補の一点最適化ではなく、より広いwalk-forward、OOF calibration、stateful blocking / replacement regretを教師側に組み込む方向へ戻る。

## 次の作業

1. `model-trade-delta` のstateful candidate examplesを、候補採用前の診断として標準化する。
2. validation foldを増やすか、別時期を混ぜたwalk-forwardで、候補が「置換で勝っているだけ」かを採用前に確認する。
3. entry/sideのhard gate追加ではなく、blocking cost / replacement regret / downside riskを教師targetまたはOOF診断に戻す。
4. validationで良いがapplyで崩れる設定を、採用候補ではなく失敗例データとして蓄積する。

## Artifacts

- standard validation base runs: `data/reports/backtests/guard_fixed_standard_validation_base/`
- standard validation high cost runs: `data/reports/backtests/guard_fixed_standard_validation_highcost/`
- standard apply base runs: `data/reports/backtests/guard_fixed_standard_apply_base/`
- standard apply high cost runs: `data/reports/backtests/guard_fixed_standard_apply_highcost/`
- top validation base runs: `data/reports/backtests/guard_fixed_top_validation_base/`
- top validation high cost runs: `data/reports/backtests/guard_fixed_top_validation_highcost/`
- top apply base runs: `data/reports/backtests/guard_fixed_entry_side_top_apply_base/`
- top apply high cost runs: `data/reports/backtests/guard_fixed_entry_side_top_apply_highcost/`
- exposure summaries: `data/reports/backtests/20260629_013143_guard_fixed_*_exposure/`, `data/reports/backtests/20260629_013144_guard_fixed_*_exposure/`
- delta summaries: `data/reports/backtests/20260629_013226_guard_fixed_standard_vs_top_*_delta/`, `data/reports/backtests/20260629_013227_guard_fixed_standard_vs_top_*_delta/`
- combined diagnostics: `data/reports/backtests/guard_fixed_entry_side_drift_diagnostics/20260629_103336_guard_fixed_entry_side_drift/`

## Verification

- fixed `model-policy`追加24 runs: OK
- `model-trade-exposure` 8 runs: OK
- `model-trade-delta` 4 runs: OK
