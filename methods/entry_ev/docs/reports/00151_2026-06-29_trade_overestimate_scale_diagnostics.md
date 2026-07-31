# Trade Overestimate Scale Diagnostics

日時: 2026-06-29 16:19 JST
更新日時: 2026-06-29 16:23 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00150` で、chronological OOFでは `q90 w2.0` が一度も発火しないことが分かった。

今回は、原因を「実際にhigh overestimate targetがない」のか、「targetはあるが予測スケールが低く潰れている」のかに分解する。また、fold-local q75 thresholdを使った最小実験で、単純なthreshold引き下げが有効かを確認する。

## 実装

`trade-overestimate-scale-diagnostics` を追加した。

出力:

- `fold_scale_metrics.csv`
- `prediction_activation_metrics.csv`
- `summary.json`

見るもの:

- fit側selected tradeのtarget分布
- holdout selected tradeのtarget / prediction分布
- fit側thresholdを超える実target件数
- selected trade予測がthresholdを超える件数
- 全prediction行のside別threshold発火件数

## Q90 Scale Diagnosis

`00148` の固定threshold long `18.8171`, short `21.1886` と、各foldのfit側target q90を比較した。

summary:

| metric | value |
|---|---:|
| profiled side folds | `6` |
| selected trades | `281` |
| selected target >= fit q90 | `36` |
| selected prediction > fit q90 | `0` |
| selected prediction > fixed q90 | `0` |
| side prediction rows | `170722` |
| side prediction > fit q90 | `0` |
| side prediction > fixed q90 | `0` |
| median selected pred max / fit q90 | `0.4428` |
| median prediction max / fit q90 | `0.5491` |

実際にはfit q90を超えるhigh targetが36件ある。しかしselected trade上のpredictionも、全prediction行のside別amountも、fit q90を一度も超えない。つまり「high targetが存在しない」のではなく、「chronological modelの予測上限がthresholdよりかなり低い」。

side別:

| holdout | side | fit q90 | holdout target q90 | holdout pred q90 | target >= fit q90 | pred > fit q90 | pred max / fit q90 |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025-02 | long | `10.9981` | `13.7232` | `4.6997` | `8` | `0` | `0.4557` |
| 2025-02 | short | `13.3550` | `12.9128` | `5.4899` | `5` | `0` | `0.4331` |
| 2025-03 | long | `12.8793` | `9.0022` | `4.5344` | `5` | `0` | `0.4020` |
| 2025-03 | short | `13.4113` | `13.4514` | `6.5417` | `4` | `0` | `0.5363` |
| 2025-04 | long | `11.0345` | `4.6987` | `4.7013` | `2` | `0` | `0.4364` |
| 2025-04 | short | `13.5405` | `26.9134` | `6.0816` | `12` | `0` | `0.4491` |

特に2025-04 shortはtarget q90 `26.9134`、target >= fit q90が12件あるのに、prediction maxはfit q90の45%程度に留まる。

## Q75 Scale Diagnosis

q90だけではthresholdが高すぎる可能性が残るため、fold-local q75も診断した。

summary:

| metric | value |
|---|---:|
| selected target >= fit q75 | `79` |
| selected prediction > fit q75 | `12` |
| side prediction > fit q75 | `13093` |
| median selected pred max / fit q75 | `0.9351` |
| median prediction max / fit q75 | `1.1160` |

q75なら発火する。ただしselected target 79件に対してprediction発火は12件だけで、捕捉は弱い。side別ではshort側がほぼ発火しない。

| holdout | side | fit q75 | target >= fit q75 | pred > fit q75 | all-row pred > fit q75 |
|---|---|---:|---:|---:|---:|
| 2025-02 | long | `4.5393` | `17` | `7` | `3416` |
| 2025-02 | short | `7.6928` | `17` | `0` | `0` |
| 2025-03 | long | `5.0677` | `13` | `2` | `439` |
| 2025-03 | short | `8.4751` | `14` | `0` | `0` |
| 2025-04 | long | `4.6392` | `2` | `3` | `9238` |
| 2025-04 | short | `9.2294` | `16` | `0` | `0` |

## Fold-Local Q75 Policy Check

各holdout月のfit側selected-trade target q75をside別thresholdにし、`lambda=2.0` を固定してpolicy接続した。

これはapply月の分布を見ないfold-local calibrationだが、結果は悪化。

| month | baseline PnL | fold-local q75 PnL | delta | baseline trades | q75 trades |
|---|---:|---:|---:|---:|---:|
| 2025-02 | `113.1642` | `97.4168` | `-15.7474` | `104` | `107` |
| 2025-03 | `27.1660` | `27.1660` | `0.0000` | `102` | `102` |
| 2025-04 | `14.3072` | `11.3792` | `-2.9280` | `75` | `76` |
| total | `154.6374` | `135.9620` | `-18.6754` | `281` | `285` |

delta診断:

- 2025-02でonly_base long/up_low_vol `-19.2860`、only_base long/range_low_vol `-14.0000`。良いlongを落とした。
- 2025-02でonly_candidate short/range_normal_vol `-11.0160`、only_candidate short/up_normal_vol `-10.4364`。悪いshortを追加した。
- 2025-04はonly_candidate short/range_low_vol `-0.7080` と、common long/up_low_volの決済差分 `-2.2200` で小幅悪化。

q75は「発火しない」問題は解くが、取引選択の質を改善しない。

## 判断

1. chronological amount modelにはrank signalが少し残るが、amount scaleは高targetを再現できない。
2. q90は発火せず、q75は発火するが悪化する。thresholdを下げるだけでは解決しない。
3. short側high targetの捕捉が特に弱い。short targetは2025-04で大きいが、prediction上限が低く、riskとして使えない。
4. 次はamount回帰の絶対値をpenaltyに使わず、high target分類、side別calibration、またはstateful/context downside targetと組み合わせたranking特徴にする。
5. fold-local q75 w2.0は不採用。`q90 w2.0` も単独標準候補へ戻さない。

## Artifacts

- q90 scale diagnostics: `data/reports/modeling/20260629_071630_trade_overestimate_chronological_scale_diagnostics/`
- q75 scale diagnostics: `data/reports/modeling/20260629_071711_trade_overestimate_chronological_scale_diagnostics_q75/`
- fold-local q75 predictions: `data/reports/modeling/20260629_1619_trade_overestimate_chronological_fold_q75_risk/`
- fold-local q75 backtests: `data/reports/backtests/20260629_trade_overestimate_chronological_fold_q75_w2p0_validation/`
- fold-local q75 delta: `data/reports/backtests/20260629_071849_trade_overestimate_chronological_fold_q75_w2p0_delta_validation/`

## 検証

- `python3 -m unittest tests.test_meta_model`: pass
- `python3 -m unittest tests.test_meta_model tests.test_backtest tests.test_docs_reports`: pass
- `git diff --check`: pass

## 次の作業

1. high-overestimate分類targetをchronological OOFで作る。thresholdはfold fit側から決め、holdout/apply分布は見ない。
2. short側のhigh target捕捉不足をside別に評価する。全体モデルで潰れるならside別modelまたはside interactionを強める。
3. amount系riskは単独penaltyではなく、stateful/context downside targetと同時にranking特徴として扱う。
