# Stateful Blocking Risk Model

日時: 2026-06-29 09:48 JST
更新日時: 2026-06-29 09:48 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00121` / `00122` で `stateful_positive_cost_value` の平均回帰scoreはbias補正には効くが、entry順位付けには弱いことが分かった。

今回は平均値回帰ではなく、次のstateful downside eventを分類targetにした。

- `positive_blocking`: candidate保有中にpositive base tradeをブロックしたか。
- `positive_replacement_regret_high`: positive opportunity costが閾値 `5` 以上か。
- `stateful_nonpositive`: candidateのstateful net valueが0以下か。

いずれも一玉制約の機会費用を直接見るためのtargetで、既存 `risk_penalty` に接続できる `risk = -probability` 列を出す。

## 実装

`trade_data.meta_model oof-stateful-risk-model` を追加した。

出力列:

- `pred_stateful_risk_<prefix>_<target>_<side>_prob`
- `pred_stateful_risk_<prefix>_<target>_<side>_risk`
- `pred_stateful_risk_<prefix>_<target>_taken_prob`

OOFは `dataset_month` をfoldにして、scored monthをfit側から外す。validation prediction parquetへはfoldごとのclassifierでrisk列を付与し、apply prediction parquetへはvalidation全体fitのfinal modelでrisk列を付与する。

artifacts:

- model: `data/reports/modeling/20260629_004108_stateful_blocking_risk_model/`
- validation `positive_replacement_regret_high`: `data/reports/backtests/stateful_blocking_risk_positive_replacement_validation/`
- validation `positive_blocking`: `data/reports/backtests/stateful_blocking_risk_positive_blocking_validation/`
- validation `stateful_nonpositive`: `data/reports/backtests/stateful_blocking_risk_nonpositive_validation/`
- apply `positive_blocking`: `data/reports/backtests/stateful_blocking_risk_positive_blocking_apply/`

## OOF Metrics

Validation examplesは254件。分類probabilityの平均はprevalenceに近く、biasは小さい。一方でAUCは全targetで0.5未満。

| target | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|
| `positive_blocking` | `0.1181` | `0.1114` | `-0.0067` | `0.1047` | `0.4878` |
| `positive_replacement_regret_high` | `0.2480` | `0.2458` | `-0.0022` | `0.1876` | `0.4869` |
| `stateful_nonpositive` | `0.3976` | `0.3973` | `-0.0004` | `0.2436` | `0.4520` |

この時点ではrank modelとしては弱い。ただし、risk penaltyはentry集合と一玉制約の経路を変えるため、OOF分類AUCだけでは採否を決めず、policy接続でも確認した。

## Validation Policy Sweep

固定条件:

- policy: `timed_ev`
- entry threshold `12`
- short offset `6`
- side margin `5`
- min entry rank `0.5`
- max predicted hold `480`
- side EV penalty: `short:down_low_vol=5`, `short:up_low_vol=10`
- profit/loss: `1.0 / 1.20`

4ヶ月validation summary:

| target | risk | sum PnL | min month PnL | trades | max DD |
|---|---:|---:|---:|---:|---:|
| baseline | `0` | `622.6486` | `138.0338` | `275` | `85.0166` |
| `positive_replacement_regret_high` | `5` | `683.7320` | `91.4356` | `249` | `59.2494` |
| `positive_replacement_regret_high` | `10` | `541.6800` | `64.3768` | `199` | `49.8704` |
| `positive_blocking` | `5` | `675.7414` | `157.0628` | `269` | `74.7688` |
| `positive_blocking` | `10` | `679.2296` | `136.8352` | `258` | `70.4296` |
| `positive_blocking` | `20` | `686.4518` | `137.3834` | `221` | `67.2204` |
| `stateful_nonpositive` | `5` | `528.5312` | `49.8230` | `216` | `55.4400` |

`positive_replacement_regret_high` は合計PnLを上げるが、2024-09を `138.0338 -> 91.4356` に壊す。`stateful_nonpositive` は取引を削りすぎる。

`positive_blocking risk=5` だけが、validationで合計、最低月、drawdownを同時に改善した。月別では2024-07を `198.1782 -> 179.1520` に削るが、2024-09 / 2024-11 / 2025-01を改善した。

## Apply Check

`positive_blocking risk=5` をapply 3ヶ月へ固定適用した。

| risk | sum PnL | min month PnL | trades | max DD |
|---:|---:|---:|---:|---:|
| `0` | `242.5008` | `-20.8252` | `426` | `122.9852` |
| `5` | `198.9860` | `-3.5260` | `417` | `128.1944` |
| `10` | `172.3982` | `-21.0158` | `403` | `121.3700` |
| `20` | `27.3248` | `-67.1952` | `370` | `117.2764` |

`risk=5` は2024-12の最低月を `-20.8252 -> -3.5260` に改善したが、2025-02を `179.2484 -> 141.2374`、2025-03を `84.0776 -> 61.2746` に削り、apply合計とmaxDDは悪化した。

## 判断

`positive_blocking` risk modelの実装は採用する。これは一玉制約の機会費用を分類targetとして扱える基盤であり、validationでは有効なcandidateを出した。

ただし、標準policyのrisk penaltyにはまだ採用しない。

理由:

- OOF AUCが `0.4878` とrank能力を示していない。
- validationでは `risk=5` が良いが、applyでは合計PnLとmaxDDが悪化した。
- 改善は「負け月の保護」と「良い月の削り」のトレードオフで、まだ汎化したedgeとは言い切れない。
- `positive_replacement_regret_high` と `stateful_nonpositive` はvalidation時点で不安定。

次にやること:

1. `positive_blocking` を標準riskではなく、候補ranking診断、regime/session別露出診断、またはrisk budget候補として残す。
2. 追加月examplesを作り、254件からsupportを増やした上で同じOOFを再評価する。
3. 分類AUCを上げるより先に、target別に「どのregimeでprobabilityが効くか」を分解する。
4. `positive_blocking risk=5` は事前登録候補として、追加walk-forward foldでは固定値で評価する。
