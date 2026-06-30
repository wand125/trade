# Replacement Prior Signal Audit

日時: 2026-06-30 10:42 JST
更新日時: 2026-06-30 10:42 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00197の次アクションとして、2024側同一family固定適用の可用性を確認したが、既存artifactだけでは同一条件にならない。
- 2025 familyの `predictions_side_guard_input.parquet` は 2025-01..12 のみ。2024の `guard_fixed_standard_validation_base` は costなし、max hold 480、risk penalty 0で、00197の coststress 260 + stateful risk5 + replacement margin10 とは別family。
- そこで、00197で見えた `gap5/budget0` replacement shortが、target monthより前のcontext signalで検知できるかを監査する `short_budget_replacement_signal_audit.py` を追加した。
- prior short side-drift alert単体では、late 2025-08..12の `gap5` replacement short `-286.9878` のうち `-133.9066` しか覆えず、`-153.0812` が残る。
- prior alert OR prior max prediction short bias `>= 0.30` なら `-192.4296` を覆い、残存は `-94.5582` まで縮む。ただしこれは executed replacement rows の削除上限で、dynamic policyの成績ではない。
- 最大の残存は `range_low_vol/ny_overlap`。このcontextは prior alert 0、prior max prediction short biasも `0.2185` 程度で、既存context drift signalでは弱い。
- 結論: context alertを強めるだけでは足りない。`up_low_vol/ny_overlap` は prior prediction biasで拾えるが、`range_low_vol/ny_overlap` には entry-level EV overestimate / NY overlap specific risk / current-month first-loss control が必要。

## Artifacts

- Replacement signal audit: `data/reports/backtests/20260630_104800_short_budget_replacement_signal_audit/`
- Input replacement rows: `data/reports/backtests/20260630_103100_short_budget_replacement_trade_audit/replacement_rows.csv`
- Reference side-drift diagnostics: `data/reports/modeling/20260629_133501_side_drift_reference_2025_01_08_coststress_260/`
- Fresh side-drift diagnostics: `data/reports/modeling/20260629_133440_side_drift_fresh_2025_09_12_coststress_260/`

## Method

追加したスクリプト:

- `scripts/experiments/short_budget_replacement_signal_audit.py`

Inputs:

- replacement rows: `delta_status == only_candidate`, `direction == short`
- prior side-drift alerts: `side_drift_alerts.csv`
- prior prediction context metrics: `prediction_group_summary.csv`
- prior selected-trade context metrics: `selected_trade_group_summary.csv`

各replacement tradeについて、同じ `combined_regime + session_regime` の直近3ヶ月だけを見て、以下を付与した。

- prior short alert count / loss-bias sum
- prior prediction short bias mean/max
- prior prediction short share and match rate
- prior selected short PnL / trade count / EV overestimate

同月alertも出力しているが、これはattribution用であり、live ruleの採用判断には使わない。

## Condition Results

Late 2025-08..12 の `global_gap5_budget0` replacement short:

| condition | covered rows | covered PnL | uncovered rows | uncovered PnL |
|---|---:|---:|---:|---:|
| prior alert >= 1 | `30` | `-133.9066` | `37` | `-153.0812` |
| prior alert loss-bias >= 10 | `8` | `-20.4700` | `59` | `-266.5178` |
| prior pred-short bias max >= 0.30 | `38` | `-127.4852` | `29` | `-159.5026` |
| prior pred-short bias mean >= 0.20 | `36` | `-125.1792` | `31` | `-161.8086` |
| prior selected short PnL < 0 | `37` | `-100.8256` | `30` | `-186.1622` |
| prior alert OR prior pred-short bias max >= 0.30 | `48` | `-192.4296` | `19` | `-94.5582` |

Late 2025-09..12 でも同じ傾向。

| condition | covered rows | covered PnL | uncovered rows | uncovered PnL |
|---|---:|---:|---:|---:|
| prior alert >= 1 | `23` | `-123.5908` | `27` | `-140.6940` |
| prior pred-short bias max >= 0.30 | `28` | `-104.7818` | `22` | `-159.5030` |
| prior alert OR prior pred-short bias max >= 0.30 | `38` | `-169.7262` | `12` | `-94.5586` |

`gap0/budget0` 側では同じ条件が良いreplacementも消しやすい。late 2025-09..12の `prior alert OR pred bias` は covered PnL `+11.4800`、uncovered `-40.0974` で、防御candidateにさらに同条件を重ねるのは危険。

## Context Results

`global_gap5_budget0`, late 2025-08..12:

| context | rows | PnL | prior alert rows | prior alert or bias rows | note |
|---|---:|---:|---:|---:|---|
| `up_low_vol/ny_overlap` | `3` | `-103.5756` | `0` | `3` | prior pred-short bias max `0.5711` で拾える |
| `range_low_vol/ny_overlap` | `8` | `-86.5792` | `0` | `1` | 既存prior context signalではほぼ拾えない |
| `range_low_vol/asia` | `23` | `-82.6692` | `23` | `23` | prior alertで拾えるが00194のalert-context budgetでは全体改善に届かなかった |
| `down_normal_vol/ny_overlap` | `2` | `-22.9200` | `0` | `0` | weak prior signal |
| `range_normal_vol/ny_overlap` | `5` | `-18.0350` | `0` | `0` | weak prior signal |

`range_low_vol/ny_overlap` の最大未検知損失は 2025-09-26 13:14 UTC の `-34.5840`。prior max prediction short biasは `0.1508`、prior short PnLは `+28.1056` で、prior context historyだけでは逆に安全に見える。

## Interpretation

- prior side-drift alertは `range_low_vol/asia` のような明確なcontext driftは拾うが、`up_low_vol/ny_overlap` や `range_low_vol/ny_overlap` のreplacement riskを十分に拾えない。
- prior prediction short biasを足すと `up_low_vol/ny_overlap` は拾える。これは context alert threshold がselected-trade lossに依存しすぎて、未取引または低support contextを見逃すため。
- それでも `range_low_vol/ny_overlap` は残る。このcontextは prior selected short PnLがプラスで、prior prediction biasも弱く、現在のprior context設計では検出困難。
- したがって、次の改善は context alertの閾値調整ではなく、entry-levelのEV過大評価、NY overlap固有のside inversion、または current-month first-loss control を使うべき。
- 今回の condition summary は「該当replacement rowを削除したら」という上限診断であり、一玉制約下の再replacementは再現しない。policy採用にはdynamic backtestが必要。

## Decision

- `short_budget_replacement_signal_audit.py` は accepted diagnostic infrastructure。
- prior alert単体は採用しない。
- prior alert OR prediction short biasは候補signalだが、標準採用しない。`gap5` replacement損失の上限削減余地を見るpreflightに留める。
- 次は `range_low_vol/ny_overlap` の未検知損失を、entry-level EV overestimateや同月first-lossで検出できるか確認する。
- 2024同一family検証は、coststress 260 + stateful risk5 + replacement margin10 の2024 prediction/backtestを生成してから行う。

## Verification

- `python3 -m py_compile scripts/experiments/short_budget_replacement_signal_audit.py tests/test_short_budget_replacement_signal_audit.py`: OK
- `python3 -m unittest tests.test_short_budget_replacement_signal_audit tests.test_short_budget_replacement_trade_audit tests.test_short_budget_fixed_rule_audit tests.test_short_budget_drift_trigger_selection tests.test_short_budget_guard_selection tests.test_docs_reports`: OK, 18 tests
- `git diff --check`: OK
- Replacement signal audit artifact generated: OK
