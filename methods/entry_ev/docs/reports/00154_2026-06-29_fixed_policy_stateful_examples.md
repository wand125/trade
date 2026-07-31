# Fixed Policy Stateful Examples

日時: 2026-06-29 16:59 JST
更新日時: 2026-06-29 16:59 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00153` では複数sourceの `stateful_candidate_examples.csv` を混ぜてsupportを増やしたが、source別target率が大きく異なり、policy接続も悪化した。

今回はsource driftを減らすため、同一固定policy pairだけを使う。

- base: `fixed_highcost_risk0`
- candidate: `fixed_highcost_risk5`
- months: `2024-11..2025-05`
- cost: `profit_multiplier=1.0`, `loss_multiplier=1.2`, spread/slippage/delay込み
- candidate target: `stateful_net`

目的は、`blocking_cost_high` / `stateful_nonpositive` が、同一policy文脈では改善するかを確認すること。

## 実装

`oof-stateful-value-model` の `--examples` 読み込みも、risk modelと同じ `read_stateful_examples()` に揃えた。前回の複数CSV/ディレクトリ対応はrisk model側には入っていたが、value model側に単一CSV読み込みが残っていたため修正した。

## Data

`model-trade-delta` で `fixed_highcost_risk5` vs `fixed_highcost_risk0` を比較し、607件のstateful examplesを作成した。

OOF学習・評価では `dataset_month` を使う。月境界をまたぐtradeがあるため、delta表示用の `month` とは数件ずれる。

| dataset month | rows | target mean | nonpositive rate | block cost high |
|---|---:|---:|---:|---:|
| 2024-11 | `73` | `+1.7808` | `0.4658` | `0.0000` |
| 2024-12 | `81` | `-0.9040` | `0.5432` | `0.0494` |
| 2025-01 | `67` | `+2.0253` | `0.4179` | `0.0149` |
| 2025-02 | `104` | `+0.3254` | `0.5096` | `0.0865` |
| 2025-03 | `103` | `-0.0885` | `0.4854` | `0.0680` |
| 2025-04 | `74` | `-0.1878` | `0.4324` | `0.0405` |
| 2025-05 | `105` | `-0.6984` | `0.4857` | `0.0286` |

2025-05を含めると、同一policyでもtarget meanは安定していない。`blocking_cost_high` は2025-02/03で高く、2025-05では低い。

## OOF Metrics

`expanding`, `min_train_months=3`。2024-11..2025-01を初期fitに使い、2025-02..2025-05をchronological OOFで評価した。

| target | candidates | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|---:|
| `positive_blocking` | `386` | `0.0881` | `0.0643` | `-0.0238` | `0.0817` | `0.4393` |
| `blocking_cost_high` | `386` | `0.0570` | `0.0400` | `-0.0170` | `0.0548` | `0.3563` |
| `replacement_regret_high` | `386` | `0.2746` | `0.2488` | `-0.0259` | `0.2004` | `0.4895` |
| `positive_replacement_regret_high` | `386` | `0.2876` | `0.2554` | `-0.0322` | `0.2075` | `0.4623` |
| `stateful_nonpositive` | `386` | `0.4819` | `0.4840` | `+0.0021` | `0.2495` | `0.5216` |

`blocking_cost_high` はAUC `0.3563` で逆方向。`stateful_nonpositive` だけがAUC `0.5216` だが、rank signalとしてはかなり薄い。

## Policy Check

既存の `walkforward_floor_lowered risk5` に、今回の追加riskを加算した。

`EV += 5 * (existing_risk + weight/5 * new_risk)` なので、既存risk5は固定し、追加riskの実効weightを `5` / `10` にした。

評価月は2025-02..2025-05。すべて highcost、`loss_multiplier=1.2`。

| label | total PnL | min month | max DD | trades |
|---|---:|---:|---:|---:|
| risk0 | `111.3582` | `-66.1420` | `259.0392` | `408` |
| baseline risk5 | `101.6610` | `-52.9764` | `224.7524` | `386` |
| blockcost w5 | `78.5882` | `-61.3746` | `228.1374` | `385` |
| blockcost w10 | `35.7162` | `-56.3702` | `226.9134` | `382` |
| nonpositive w5 | `-88.3904` | `-140.8344` | `234.8824` | `295` |
| nonpositive w10 | `-96.3226` | `-74.7448` | `232.9536` | `196` |

月別:

| label | 2025-02 | 2025-03 | 2025-04 | 2025-05 |
|---|---:|---:|---:|---:|
| baseline risk5 | `113.1642` | `27.1660` | `14.3072` | `-52.9764` |
| blockcost w5 | `126.7486` | `23.1990` | `-9.9848` | `-61.3746` |
| blockcost w10 | `86.3484` | `-12.6192` | `18.3572` | `-56.3702` |
| nonpositive w5 | `85.9190` | `-27.1434` | `-6.3316` | `-140.8344` |
| nonpositive w10 | `86.8442` | `-51.2616` | `-57.1604` | `-74.7448` |
| risk0 | `141.4436` | `60.2172` | `-24.1606` | `-66.1420` |

## 判断

1. 同一固定policyに絞っても、`blocking_cost_high` / `stateful_nonpositive` の追加riskは標準採用しない。
2. `blocking_cost_high` はOOF AUCが逆方向で、policyでもbaseline risk5を超えない。
3. `stateful_nonpositive` はAUC `0.5216` と薄いsignalがあるが、policyでは取引を削りすぎて大きく悪化した。
4. 高コスト2025-02..2025-05では、risk0のtotal PnL `111.3582` がbaseline risk5 `101.6610` を上回る。一方risk5はmin monthとmax DDを改善するため、利益最大化signalではなく防御signalとして扱うのが妥当。
5. stateful examplesの追加量だけでは改善しない。次はcandidate差分targetではなく、selected trade全体のEV過大評価・exit timing・context floorを、月外OOFで校正する方向へ戻す。

## Artifacts

- fixed highcost delta: `data/reports/backtests/20260629_075516_fixed_highcost_risk5_vs_risk0_wf_examples/`
- combined validation/apply predictions: `data/reports/modeling/20260629_fixed_highcost_wf_predictions_combined/`
- stateful risk model: `data/reports/modeling/20260629_075638_stateful_risk_fixed_highcost_risk5_vs_risk0_expanding_min3/`
- combined risk predictions and summaries: `data/reports/modeling/20260629_fixed_highcost_wf_combined_risk/`
- policy checks:
  - `data/reports/backtests/20260629_fixed_highcost_wf_nonpositive_w5p0_2025_02_05/`
  - `data/reports/backtests/20260629_fixed_highcost_wf_nonpositive_w10p0_2025_02_05/`
  - `data/reports/backtests/20260629_fixed_highcost_wf_blockcost_w5p0_2025_02_05/`
  - `data/reports/backtests/20260629_fixed_highcost_wf_blockcost_w10p0_2025_02_05/`

## 検証

- `python3 -m trade_data.backtest model-trade-delta`: pass
- `python3 -m trade_data.meta_model oof-stateful-risk-model`: pass
- `python3 -m trade_data.backtest model-policy`: pass, 16 runs
- `python3 -m unittest tests.test_meta_model tests.test_backtest tests.test_docs_reports`: pass, 130 tests
- `python3 -m py_compile src/trade_data/meta_model.py`: pass
- `python3 -m trade_data.meta_model oof-stateful-value-model --help`: pass
- `git diff --check`: pass

## 次の作業

1. `blocking_cost_high` / `stateful_nonpositive` のrisk直結は止める。
2. risk5は採用候補ではなく、防御diagnosticとして分離する。利益最大化ではrisk0が勝つ月集合がある。
3. 次はselected tradeの `common` 損失に戻り、EV overestimate residual、exit timing target、context prior floorを組み合わせた校正を検証する。
