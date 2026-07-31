# High-stress Cost Selection Failure

日時: 2026-06-29 04:14 JST
更新日時: 2026-06-29 04:14 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00092` ではmoderate cost validationでcandidate selectionを行ったが、selection topは固定holdout cost stressに届かなかった。

今回はvalidation側にもhigh cost scenarioを追加し、base + moderate + highを同時に満たす候補を選ぶ。さらに同じrule set gridをholdoutのmoderate/high costでも横断評価し、validation stress selectionが未来月stressへ外挿できるか確認する。

## 実装メモ

`model-candidate-selection` に `--min-base-folds` / `--min-cost-folds` を追加した。

理由は、`--min-folds` だけではbase/no-cost fold数とcost scenario fold数が異なる場合に誤用しやすいため。今回、baseは4ヶ月、costはmoderate/highの `4ヶ月 x 2 scenario = 8 folds` なので、明示的に `--min-base-folds 4 --min-cost-folds 8` と指定できるようにした。

互換性は維持する。新引数未指定時は従来どおり `--min-folds` をbase/cost両方に使う。

## Validation High Cost

high cost condition:

- spread: `0.2`
- slippage: `0.1`
- execution delay: `1`

Validation high costでも `down5,up10,range5` がtopだった。

| rule set | high-cost min pnl | high-cost sum pnl | min trades | max drawdown | max side share |
|---|---:|---:|---:|---:|---:|
| `down5,up10,range5` | `107.1572` | `561.4022` | `66` | `85.1858` | `0.8732` |
| `down5,up10` | `96.8776` | `500.5422` | `65` | `88.9514` | `0.8462` |
| `down5,up15` | `94.2442` | `456.4956` | `70` | `101.5464` | `0.8143` |
| `down5,range5` | `86.0172` | `503.7662` | `57` | `114.6436` | `0.8594` |
| `down5,up15,range10` | `83.7792` | `504.7462` | `70` | `120.1644` | `0.8857` |
| none | `68.5458` | `363.5058` | `24` | `66.5928` | `0.7188` |

## Explicit Fold Selection

`--min-base-folds 4 --min-cost-folds 8` でbase 4fold、moderate+high cost 8foldを同時に通すselectionを実行した。

Strict condition:

- `max_drawdown=100`
- `min_base_adjusted_pnl_per_fold=80`
- `min_cost_adjusted_pnl_per_fold=50`
- `min_trades_per_fold=50`
- `max_short_trade_share=0.65`
- `max_side_trade_share=0.90`

Eligibleは3候補。

| rule set | eligible | base min pnl | cost min pnl | cost sum pnl | max drawdown | max side share |
|---|---:|---:|---:|---:|---:|---:|
| `down5,up10,range5` | yes | `138.3706` | `107.1572` | `1182.7684` | `86.9156` | `0.8732` |
| `down5,up10` | yes | `138.0338` | `96.8776` | `1060.7086` | `88.9514` | `0.8462` |
| `up10,range10` | yes | `104.7616` | `51.4730` | `837.6116` | `99.4002` | `0.8571` |

Near-top risk diagnostic (`max_drawdown=125`, `near_top_cost_pnl_tolerance=30`) では `down5,up10` がtopになる。これはrisk score上は `down5,up10,range5` よりよいが、cost min pnlは `96.8776` でtopより低い。

## Holdout Grid Stress

同じrule set gridを固定holdout 2024-12 / 2025-02 / 2025-03 のmoderate/high costで横断評価した。

全scenario、全holdout月のmin pnlで見ると、全候補に負け月が残る。

| rule set | holdout scenarios | min pnl | sum pnl | max drawdown | max side share |
|---|---:|---:|---:|---:|---:|
| `down5,up10,range5` | `9` | `-32.4176` | `147.1338` | `181.6922` | `0.6667` |
| `down10,up10,range10` | `9` | `-41.0256` | `569.9690` | `127.9822` | `0.7398` |
| `down5,up15,range10` | `9` | `-53.7684` | `170.0336` | `144.4880` | `0.6929` |
| `down5,up10,range10` | `9` | `-53.8458` | `360.8382` | `130.2018` | `0.7311` |
| `down5,up10` | `9` | `-57.7402` | `473.2982` | `132.5332` | `0.6593` |
| none | `9` | `-84.0066` | `-264.1138` | `118.9336` | `0.9048` |

Cost scenario別:

| scenario | best min-pnl rule | min pnl | sum pnl | note |
|---|---|---:|---:|---|
| base | `down5,up15,range10` | `10.0758` | `175.8862` | zero-costでは前回候補が最良 |
| moderate | `down5,up10,range5` | `-11.7670` | `53.2806` | cost-aware topだが2024-12で負け |
| high | `down5,up10,range5` | `-32.4176` | `-31.6628` | high cost合計がマイナス |

`down10,up10,range10` は全scenario min pnlではtopに劣るが、holdout全scenario合計 `569.9690` とmax drawdown `127.9822` は相対的に良い。validation rankingはこの外挿を拾えていない。

## 判断

high-stress validation selectionを入れても、標準採用できる候補はまだない。

重要な反省:

- validation high costでは `down5,up10,range5` がかなり強いが、holdout high costでは合計 `-31.6628` へ落ちる。
- validationのmax drawdownは `86.9156` だが、holdout stressでは `181.6922` まで拡大する。
- near-top risk rankingはvalidation上 `down5,up10` を選び、strict min-pnl rankingとは異なる候補を出せる。ただしholdoutでは `down10,up10,range10` のほうが合計とdrawdownのバランスが良く、既存risk scoreだけでは不足。

次は、candidate selectionの順位付けに「cost min pnl」だけでなく、cost scenario合計、drawdown max、group損失、EV overestimateを同時に扱う。ただし、今回のholdout結果を直接最適化に使うとpost-hocになるため、まずvalidation fold内でstress-aware rankingを定義し、次の未使用holdout月で確認する。

## Artifacts

- high cost validation sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_validation_highcost/`
- holdout moderate cost sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_holdout_midcost_sweep/`
- holdout high cost sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_holdout_highcost_sweep/`
- explicit-fold selection: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_cost_aware_selection_explicit_folds/20260628_191348_model_candidate_selection/`
- strict highstress v2 selection: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_cost_aware_selection_strict_highstress_v2/20260628_191218_model_candidate_selection/`
- near-top highstress v2 selection: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_cost_aware_selection_near_top_highstress_v2/20260628_191219_model_candidate_selection/`

## Verification

- `PYTHONPATH=src python3 -m trade_data.backtest model-sweep`: OK for validation high cost and holdout mid/high sweeps
- `PYTHONPATH=src python3 -m trade_data.backtest model-candidate-selection`: OK with `--min-base-folds 4 --min-cost-folds 8`
- `PYTHONPATH=src python3 -m trade_data.backtest model-candidate-selection --help`: OK, new options shown
- `PYTHONPATH=src python3 -m unittest tests.test_backtest`: OK, 58 tests
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`: OK, 1 test
- `PYTHONPATH=src python3 -m unittest discover tests`: OK, 139 tests
- `git diff --check`: OK
