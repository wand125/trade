# Normal Vol Time Risk Validation

日時: 2026-06-29 05:48 JST
更新日時: 2026-06-29 05:48 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00100` の2025-04 failureでは、損失が `short:range_normal_vol`, `short:up_normal_vol`, `long:range_normal_vol`, `rollover`, `ny_late` に集中した。

ただし2025-04へ直接合わせるとpost-hocになるため、今回は代表4ヶ月validation (`2024-07`, `2024-09`, `2024-11`, `2025-01`) だけで、normal-vol / time-session risk ruleに台地があるかを確認する。

## 実装

`model-candidate-selection --plateau-column side_ev_penalty_rules` がCLI上は許可されていたが、実装が数値plateau専用だったため文字列rule setで落ちた。

このため `plateau_support_counts` を修正した。

- 数値plateau列: 従来通り `plateau_radius` 内のeligible近傍を数える。
- カテゴリplateau列: 同じカテゴリ値のeligible行を数える。

今回のselectionでは `min_plateau_neighbors=0` なので、カテゴリsupportは採用条件ではなく、文字列rule setを扱えるようにする互換修正として使った。

## Grid

固定policy:

- policy: `timed_ev`
- entry threshold: `12`
- long offset: `0`
- short offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- profit/loss multiplier: `1.0 / 1.20`
- holding: `pred_*_exit_event_time_bin_expected_minutes`
- holding cap: `480`

全候補は既存low-vol short penaltyを含む。

baseline:

- `short:down_low_vol:5`
- `short:up_low_vol:10`
- `short:range_low_vol:5`

追加候補:

- `short_norm5`: `short:range_normal_vol:5`, `short:up_normal_vol:5`
- `short_norm10`: `short:range_normal_vol:10`, `short:up_normal_vol:10`
- `long_range5`: `long:range_normal_vol:5`
- `long_range10`: `long:range_normal_vol:10`
- `time5`: both sides `rollover:5`, `ny_late:5`
- 上記の組み合わせ

high costは `spread=0.2`, `slippage=0.1`, `delay=1`。

## Candidate Selection

Selection条件:

- base folds: `4`
- high cost folds: `4`
- min trades per fold: `10`
- max forced exit rate: `0.10`
- max drawdown: `500`
- min base/cost pnl per fold: `0`
- rank mode: `stress_score`
- near-top cost pnl tolerance: `50`

| rule | eligible | base min | base sum | cost min | cost sum | max DD | dir-session min | dir-combined min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `time5` | true | `144.6684` | `644.3098` | `125.4900` | `552.7068` | `95.9110` | `-51.3110` | `-33.1490` |
| `long_range5` | true | `132.1532` | `644.5504` | `120.8868` | `533.0916` | `99.4726` | `-27.5448` | `-73.6082` |
| `lowvol_base` | true | `145.5682` | `673.9120` | `120.5842` | `562.8784` | `97.1906` | `-26.7204` | `-53.0622` |
| `long_range10` | true | `116.6478` | `640.9242` | `97.8728` | `532.9692` | `99.4726` | `-31.1628` | `-50.4230` |
| `short_norm5+long_range5+time5` | true | `88.9686` | `578.2488` | `67.8808` | `491.2668` | `95.9330` | `-63.4950` | `-54.8362` |
| `short_norm5+long_range5` | true | `68.8612` | `588.6994` | `42.5942` | `497.5062` | `108.9302` | `-74.1122` | `-96.8242` |
| `short_norm10+long_range10+time5` | true | `30.8194` | `335.1254` | `9.9878` | `251.8930` | `123.3240` | `-76.2620` | `-60.7320` |
| `short_norm5` | false | `18.6646` | `508.7186` | `-3.2670` | `414.0132` | `135.6824` | `-83.5076` | `-106.4422` |
| `short_norm10+long_range10` | false | `18.1906` | `465.6004` | `-6.5646` | `367.5908` | `138.0084` | `-75.7556` | `-90.5048` |
| `short_norm10` | false | `27.2070` | `477.8692` | `-6.8014` | `381.8492` | `155.3244` | `-65.5996` | `-90.9590` |

## 判断

normal-volへの直接short減点は採用しない。

- `short_norm5` / `short_norm10` はhigh cost最低月がマイナスへ落ちる。
- short normal-volを強く落とすとshort shareは下がるが、validation PnLとdrawdownが悪化する。
- 2025-04 failureの見た目に合わせて `short:range_normal_vol` / `short:up_normal_vol` を直接減点するのは、validation上でも台地になっていない。

`time5` は診断候補として残す。

- high cost min pnlは `120.5842 -> 125.4900` に小改善した。
- ただしbase minは `145.5682 -> 144.6684`、base sumは `673.9120 -> 644.3098`、cost sumも `562.8784 -> 552.7068` に下がる。
- 改善は小さく、明確な新edgeではない。

`long_range5` も診断候補止まり。

- cost minは `120.8868` とbaselineをわずかに上回るが、base min/sumとcost sumを削る。

次の方針:

- normal-vol side EV penaltyを標準候補にしない。
- `time5` / `long_range5` は、標準採用ではなくrisk診断・ranking特徴として残す。
- 次はruleを増やすより、session/regime別の選択失敗を教師化する。候補は `wrong_side`, `large_loss`, `range_normal_vol selected failure`, `rollover/ny_late selected failure` の分類targetまたはOOF診断特徴。
- log-derived holding比較は別枠で、log列入りartifactを再生成してから行う。

## Artifacts

- base sweeps: `data/reports/backtests/normal_time_risk_validation_base/`
- high cost sweeps: `data/reports/backtests/normal_time_risk_validation_highcost/`
- candidate selection: `data/reports/backtests/normal_time_risk_validation_selection/20260628_204722_model_candidate_selection/`
- detail summary: `data/reports/backtests/normal_time_risk_validation_rule_summary.csv`
- group summary: `data/reports/backtests/normal_time_risk_validation_rule_group_summary.csv`

## Verification

- `python3 -m trade_data.backtest model-sweep`: OK for 8 validation sweeps
- `python3 -m trade_data.backtest model-candidate-selection`: OK
- metrics aggregation: OK
- `python3 -m py_compile src/trade_data/backtest.py tests/test_backtest.py`: OK
- `python3 -m unittest tests.test_backtest.BacktestTests.test_plateau_support_counts_handles_categorical_sweep_key tests.test_backtest.BacktestTests.test_candidate_selection_combines_cost_and_plateau_gates`: OK, 2 tests
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 65 tests
- `python3 -m unittest discover tests`: OK, 147 tests
- `git diff --check`: OK
