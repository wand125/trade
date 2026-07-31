# Model Trade Delta Parent Pairing

日時: 2026-06-29 10:40 JST
更新日時: 2026-06-29 10:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00128` で `model-trade-delta` を候補採用前の標準診断にする方針にした。しかし実運用上は、複数月の `model-policy` runが入った親ディレクトリを渡すと、手作業で月別runを並べる必要があった。

今回は親ディレクトリをそのまま渡しても、base/candidateを安全に月別ペアリングできるようにする。

## 実装

`src/trade_data/backtest.py` に以下を追加した。

- `model_policy_run_month_label`
- `map_model_policy_runs_by_month`
- `pair_model_trade_delta_run_paths`

`model-trade-delta` は、親ディレクトリを展開したあと、各runの `config.json` 内 `backtest_config.evaluation_start` から月を取得し、base/candidate runを月で対応付ける。月が重複する場合や、base/candidateの月集合が一致しない場合はfail-fastする。

READMEにも、親ディレクトリ比較ではファイル名やmtimeではなく、run内部の `config.json` の評価月でペアリングすることを追記した。

## 実データ確認

`00128` と同じ標準候補 vs validation top候補を、親ディレクトリ指定だけで再実行した。

| split | cost | base PnL | candidate PnL | delta |
|---|---|---:|---:|---:|
| validation | base | `622.6486` | `685.5456` | `+62.8970` |
| validation | high cost | `500.5422` | `586.9640` | `+86.4218` |
| apply | base | `246.8762` | `-42.4328` | `-289.3090` |
| apply | high cost | `132.6970` | `-157.7340` | `-290.4310` |

これは `00128` の手作業ペアリング結果と一致する。これで候補採用前のstateful delta診断を、親ディレクトリ指定だけで再実行できる。

## 判断

`model-trade-delta` の親ディレクトリ比較を標準診断フローに使う。

扱い:

- 候補採用前に、validationだけでなくapply/holdout側で `only_base`, `only_candidate`, `common`, blocking group, `stateful_candidate_examples.csv` を確認する。
- 月のペアリングは `config.json` の `evaluation_start` を正とする。ディレクトリ名やファイル更新時刻には依存しない。
- 今回は診断基盤の改善であり、trade policy自体は変更しない。

## Artifacts

- validation base delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta/`
- validation high cost delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta/`
- apply base delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta/`
- apply high cost delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta/`

## Verification

- targeted parent-dir test: OK
- existing trade-delta test: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 75 tests
- `git diff --check`: OK
