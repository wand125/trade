# Guard Fixed Entry Side Grid

日時: 2026-06-29 10:23 JST
更新日時: 2026-06-29 10:23 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00126` でMLP holding guardをCLI標準にした。次に、guard固定後にentry/sideパラメータを少し動かしても、validationだけでなくapplyへ外挿する候補があるか確認する。

これは2025-04を見て候補を作る試行ではなく、validation 4ヶ月で候補を選び、apply 4ヶ月へ固定適用する。

## 条件

共通:

- policy: `timed_ev`
- loss multiplier: `1.20`
- EV columns: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- holding guard: CLI auto default, resolved `min_valid_predicted_hold_minutes=30`
- max predicted hold: `480`
- min entry rank: `0.5`

validation grid:

- months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- entry thresholds: `10,12,14,16`
- short offsets: `4,6,8`
- side margins: `3,5,7`
- short low-vol rule sets: `none`, `down5/up10`, `down5/up10/range5`, `down10/up10`
- cost cases: base and high cost (`spread=0.2`, `slippage=0.1`, `delay=1`)

candidate selection:

- base folds: `4/4`
- high-cost folds: `4/4`
- min trades per fold: `10`
- max forced exit rate: `0.05`
- max drawdown: `300`
- min adjusted PnL per fold: `0`
- max side trade share: `0.9`
- rank mode: `stress_score`

## Validation

144候補中82候補がeligible。validation topは以下。

| candidate | entry | short offset | margin | short low-vol penalty | base sum | base min | high sum | high min | min trades | max DD |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| validation top | `14` | `4` | `5` | `down5/up10/range5` | `685.5456` | `154.4590` | `586.9640` | `138.6648` | `50` | `60.1244` |
| current standard | `12` | `6` | `5` | `down5/up10` | `622.6486` | `138.0338` | `500.5422` | `96.8776` | `65` | `88.9514` |

validation上はtop候補が標準を上回る。特にhigh costの最低月が `96.8776 -> 138.6648` に改善し、drawdownも下がる。

## Apply Fixed

validation top候補を、apply 4ヶ月 (`2024-12`, `2025-02`, `2025-03`, `2025-04`) へ固定適用した。

| candidate | split | cost | sum PnL | min month | min trades | max DD | max forced rate |
|---|---|---|---:|---:|---:|---:|---:|
| current standard | apply | base | `246.8762` | `-18.7168` | `77` | `249.9600` | `0.0390` |
| current standard | apply | high cost | `132.6970` | `-34.3748` | `78` | `259.0392` | `0.0380` |
| validation top | apply | base | `-42.4328` | `-50.1562` | `63` | `234.9210` | `0.0476` |
| validation top | apply | high cost | `-157.7340` | `-69.2394` | `65` | `242.9664` | `0.0462` |

validation top候補の月別:

| month | base PnL | high cost PnL | base trades | high trades |
|---|---:|---:|---:|---:|
| `2024-12` | `-9.4598` | `-28.8162` | `63` | `65` |
| `2025-02` | `-7.9322` | `-47.7828` | `82` | `82` |
| `2025-03` | `25.1154` | `-11.8956` | `92` | `92` |
| `2025-04` | `-50.1562` | `-69.2394` | `69` | `69` |

2025-04の高回転破綻は抑えられているが、2024-12 / 2025-02 / 2025-04でNoTradeを下回り、high costでは4ヶ月すべてマイナスになった。

## 判断

validation top候補は標準採用しない。

理由:

- validationでは標準候補より強いが、applyでは現行標準guard候補を大きく下回る。
- `range_low_vol` 追加penaltyと `entry=14/short offset=4` は、validation fold内の損失分布に合いすぎている可能性が高い。
- guardはholdingの外挿破綻を止めるが、entry/side EVの汎化問題は解決していない。

次はentry threshold / side penaltyの探索を増やさず、OOF calibration、downside feature、regime drift診断へ戻る。

## Artifacts

- validation base sweeps: `data/reports/backtests/guard_fixed_entry_side_validation_base/`
- validation high cost sweeps: `data/reports/backtests/guard_fixed_entry_side_validation_highcost/`
- candidate selection: `data/reports/backtests/guard_fixed_entry_side_candidate_selection/20260629_012117_model_candidate_selection/`
- apply top base: `data/reports/backtests/guard_fixed_entry_side_top_apply_base/`
- apply top high cost: `data/reports/backtests/guard_fixed_entry_side_top_apply_highcost/`
- comparison summary: `data/reports/backtests/guard_fixed_entry_side_candidate_selection/20260629_012117_model_candidate_selection/top_vs_standard_validation_apply.csv`

## Verification

- `model-sweep` validation 8 runs completed.
- `model-candidate-selection`: 144 candidates, 82 eligible.
- `model-policy` fixed apply 8 runs completed.
- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
