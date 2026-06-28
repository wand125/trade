# Jackknife Holdout Gap

日時: 2026-06-29 07:16 JST
更新日時: 2026-06-29 07:16 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00108` ではjackknife選定候補がvalidation内部のleft-out foldをすべて通過した。ただし、これは未知regimeの代替ではない。

今回はjackknifeで選ばれた候補を、既存の2024-12 / 2025-02 / 2025-03 holdout stressへ固定監査する。既存holdoutはすでに見ているため、採用候補を選び直すためではなく、validation内部安定性と実holdout崩れのギャップを確認するために使う。

## 実装メモ

`model-holdout-audit` の再利用中に2点修正した。

- `normalize_sweep_key_columns` で `long_holding_fallback_column` / `short_holding_fallback_column` を文字列keyとして正規化する。CSVで空値がNaN/floatになるとmerge key dtypeがずれるため。
- validation summaryをholdout summaryへmergeする前に、`SWEEP_KEY_COLUMNS` で重複candidate keyを落とす。jackknife summaryは同じcandidateが複数left-out foldで選ばれるため、candidate単位のholdout監査では重複行を出さない。

## Holdout Audit

対象:

- validation summary: `00108` のjackknife w0/w1 metrics
- holdout: `component_fixed_weighted_short_lowvol_combo_holdout_sweep`
- holdout midcost: `component_fixed_weighted_short_lowvol_combo_holdout_midcost_sweep`
- holdout highcost: `component_fixed_weighted_short_lowvol_combo_holdout_highcost_sweep`
- pass条件: `min_holdout_cases=9`, `min_trades_per_case=50`, `max_forced_exit_rate=0.05`, `max_drawdown=250`, `min_adjusted_pnl_per_case=0`

`near_top_pnl_stability_weight=0` と `1.0` のjackknife候補監査結果は同じ。

| candidate | cases | pass cases | min pnl | sum pnl | positive rate | max DD | audit eligible |
|---|---:|---:|---:|---:|---:|---:|---:|
| `down5,up10` | `9` | `6` | `-57.7402` | `473.2982` | `0.6667` | `132.5332` | no |
| `down5,range5` | `6` | `2` | `-125.8666` | `-271.6002` | `0.3333` | `151.5020` | no |

### Case Breakdown

`down5,up10`:

| month | cost | adjusted pnl | trades | max DD | short share | worst direction/regime pnl |
|---|---|---:|---:|---:|---:|---:|
| 2024-12 | base | `-20.8252` | `92` | `122.9852` | `0.3804` | `-48.9630` |
| 2024-12 | mid | `-36.7696` | `94` | `125.4046` | `0.3723` | `-50.4036` |
| 2024-12 | high | `-57.7402` | `94` | `132.5332` | `0.3723` | `-54.9236` |
| 2025-02 | base | `179.2484` | `182` | `77.0722` | `0.6593` | `-28.1040` |
| 2025-02 | mid | `131.8142` | `182` | `86.4574` | `0.6593` | `-29.3280` |
| 2025-02 | high | `91.7348` | `182` | `91.7774` | `0.6593` | `-30.0480` |
| 2025-03 | base | `84.0776` | `152` | `65.4978` | `0.5461` | `-41.2714` |
| 2025-03 | mid | `67.5572` | `152` | `63.6272` | `0.5461` | `-42.0954` |
| 2025-03 | high | `34.2010` | `152` | `74.0246` | `0.5461` | `-47.2108` |

`down5,range5`:

| month | cost | adjusted pnl | trades | max DD | short share | worst direction/regime pnl |
|---|---|---:|---:|---:|---:|---:|
| 2024-12 | mid | `-107.5422` | `83` | `138.7776` | `0.4096` | `-60.9236` |
| 2024-12 | high | `-125.8666` | `83` | `151.5020` | `0.4096` | `-63.2836` |
| 2025-02 | mid | `-31.7992` | `145` | `143.1132` | `0.7586` | `-24.7888` |
| 2025-02 | high | `-63.7498` | `145` | `150.1622` | `0.7586` | `-29.0688` |
| 2025-03 | mid | `43.2392` | `133` | `66.0400` | `0.6015` | `-36.5560` |
| 2025-03 | high | `14.1184` | `133` | `73.6784` | `0.6015` | `-39.3848` |

`down5,range5` はholdout base sweep側に候補がなく、coverageが6caseに留まる。この時点で標準候補にはできない。

## 判断

jackknife診断は有用だが、既存holdout stressの崩れを解消しない。

重要な点:

- validation内部ではleft-out foldを通過しても、既存holdoutの2024-12で `down5,up10` は全cost負け。
- 2024-12の負けは取引数不足ではなく、92-94 tradesの実損失。NoTradeに負けている。
- `down5,range5` はjackknifeで一度選ばれたが、holdout coverage不足かつ既存holdoutでは明確に悪い。
- したがって、PnL stabilityやjackknifeで候補rankingを少し補強しても、標準policy昇格には届かない。

次は候補rankingのweight調整ではなく、2024-12型の崩れをvalidation側で事前検知できる特徴へ戻る。具体的には、regime/session failure、month-level regime mix、またはentry/exitの局所損失を、候補選定の後段診断だけでなく教師・特徴側に戻して扱う。

## Artifacts

- jackknife holdout audit w0: `data/reports/backtests/jackknife_candidate_holdout_audit_w0/20260628_221551_model_holdout_audit/metrics.csv`
- jackknife holdout audit w1: `data/reports/backtests/jackknife_candidate_holdout_audit_w1/20260628_221551_model_holdout_audit/metrics.csv`

## Verification

- `python3 -W ignore -m unittest tests.test_backtest.BacktestTests.test_holdout_audit_requires_all_holdout_cases_to_pass`: OK
- `python3 -m trade_data.backtest model-holdout-audit`: OK for jackknife w0/w1
- `python3 -W ignore -m unittest tests.test_backtest tests.test_docs_reports`: OK, 67 tests
- `python3 -W ignore -m unittest discover tests`: OK, 153 tests
- `git diff --check`: OK
