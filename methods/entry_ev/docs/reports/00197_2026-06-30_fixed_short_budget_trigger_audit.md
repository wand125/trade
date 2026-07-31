# Fixed Short Budget Trigger Audit

日時: 2026-06-30 10:31 JST
更新日時: 2026-06-30 10:31 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00196の次ステップとして、探索済み条件を固定し、`gap5/budget0 -> gap0/budget0` triggerを再探索なしで監査するスクリプトを追加した。
- 固定ルールは primary `short_gap_threshold=5/context_entry_budget=0`、defensive `short_gap_threshold=0/context_entry_budget=0`、trigger `recent_short_losing_months >= 1`、recent window 3ヶ月。
- min_train 4/5/6では trigger が primary / defensive の両方を上回った。min4は total `+232.2466`, worst `-46.0150`, short PnL `+154.7572`。
- min_train 7/8では遅い期間だけが評価対象になり、triggerはほぼ defensive `gap0/budget0` へ倒れる。min8は total `-15.0104`, worst `-45.4774` でNoTrade未満。
- `gap5/budget0` の late replacement shortをtrade単位で分解した。late 2025-08..12の candidate-only shortは `gap5` が67件 `-286.9878`、`gap0` は16件 `-38.6214`。
- 結論: fixed triggerは単なるall-window後知恵よりは説明力があるが、late-onlyでは利益policyではなくtail control。標準採用せず、追加未使用月または2024側へ同じ固定ルールを適用する。

## Artifacts

- Fixed trigger audit: `data/reports/backtests/short_budget_fixed_rule_gap5_to_gap0_audit/`
- Replacement trade audit: `data/reports/backtests/20260630_103100_short_budget_replacement_trade_audit/`
- Source budget sweep: `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/`
- Gap0 delta: `data/reports/backtests/20260630_011435_global_gap0_budget0_vs_baseline_delta/`
- Gap5 delta: `data/reports/backtests/20260630_011534_global_gap5_budget0_vs_baseline_delta/`

## Method

追加したスクリプト:

- `scripts/experiments/short_budget_fixed_rule_audit.py`
- `scripts/experiments/short_budget_replacement_trade_audit.py`

固定ルール監査は、target monthの成績をtrigger判定に使わない。対象月より前の月だけで `recent_short_losing_months` を計算し、triggeredなら defensive `gap0/budget0`、そうでなければ primary `gap5/budget0` を選ぶ。

replacement監査は `model-trade-delta` の `trade_delta_rows.csv` から `delta_status == only_candidate`、`direction == short` だけを抽出する。これはguard後に空いた一玉制約の時間へ入ってきた代替shortを測るためで、削除されたbase tradeとは別に読む。

## Fixed Rule Results

| min_train | target months | primary total | defensive total | trigger total | trigger worst | trigger short |
|---:|---|---:|---:|---:|---:|---:|
| 4 | 2025-05..12 | `-30.4328` | `+150.3206` | `+232.2466` | `-46.0150` | `+154.7572` |
| 5 | 2025-06..12 | `-77.7866` | `+130.5872` | `+184.8928` | `-46.0150` | `+61.3964` |
| 6 | 2025-07..12 | `-236.3678` | `-33.6746` | `+26.3116` | `-46.0150` | `+31.2082` |
| 7 | 2025-08..12 | `-323.7048` | `-47.0628` | `-61.0254` | `-46.0150` | `-52.5840` |
| 8 | 2025-09..12 | `-277.6898` | `-15.0104` | `-15.0104` | `-45.4774` | `-28.6174` |

min4では、2025-05..08は `gap5/budget0`、2025-09..12は `gap0/budget0` を選ぶ。これは00191の構造と一致する。min8では最初から prior deterioration が見えるため、全target月で `gap0/budget0` になり、tailは小さいが利益は残らない。

`train_window_months=0,4,6,8` は有効範囲ではほぼ同じ結果になった。triggerが直近3ヶ月だけを見るためで、ここは過去window長への過度な感度が低いという確認になる。

## Replacement Short Audit

| candidate | window | rows | total PnL | loss count | win rate | worst trade | mean EV overestimate |
|---|---|---:|---:|---:|---:|---:|---:|
| `gap0/budget0` | 2025-08..12 | `16` | `-38.6214` | `9` | `0.4375` | `-31.4844` | `17.0870` |
| `gap0/budget0` | 2025-09..12 | `10` | `-28.6174` | `6` | `0.4000` | `-31.4844` | `18.0931` |
| `gap5/budget0` | 2025-08..12 | `67` | `-286.9878` | `50` | `0.2537` | `-53.0160` | `23.9431` |
| `gap5/budget0` | 2025-09..12 | `50` | `-264.2848` | `37` | `0.2600` | `-53.0160` | `25.2724` |

月別では `gap5/budget0` の replacement short loss は 2025-09 が最大で、26件 `-182.3932`。次が2025-11の4件 `-59.0240`。2025-10/12にも小さな損失が残る。

`gap5/budget0` late 2025-08..12 の主な損失context:

| combined regime | session | rows | total PnL | loss count | mean EV overestimate |
|---|---|---:|---:|---:|---:|
| `up_low_vol` | `ny_overlap` | `3` | `-103.5756` | `3` | `50.1571` |
| `range_low_vol` | `ny_overlap` | `8` | `-86.5792` | `7` | `29.2861` |
| `range_low_vol` | `asia` | `23` | `-82.6692` | `19` | `24.2982` |
| `down_normal_vol` | `ny_overlap` | `2` | `-22.9200` | `2` | `27.6716` |
| `range_normal_vol` | `ny_overlap` | `5` | `-18.0350` | `4` | `22.1545` |

`gap0/budget0` では同じlate windowの最大損失が `range_normal_vol/ny_overlap` 9件 `-36.4554` に縮む。`gap5` は early opportunityを残せる一方、lateでは `up_low_vol/ny_overlap` と `range_low_vol` のreplacement shortに過大EVを与えている。

## Interpretation

- `gap5/budget0 -> gap0/budget0` triggerは、min4..6では primaryのearly利益と defensiveのlate防御をつなげている。
- ただし min7..8のように評価対象がlateだけになると、triggerは防御ruleに変わるだけで利益を作れない。
- `gap5` late failureは単にtrade数が多いだけではなく、mean EV overestimateが `23.9431`、worst contextsで `29..50` 台まで上がる。これはentry sideの過信とreplacement riskが同時に起きている。
- `gap0` はreplacement shortを消し切っていないが、件数と損失の尾部を大きく縮めている。今の段階では、`gap0/budget0` は利益最大化候補ではなく「short drift時の退避baseline」として扱うのが妥当。

## Decision

- `short_budget_fixed_rule_audit.py` と `short_budget_replacement_trade_audit.py` は accepted infrastructure。
- fixed `gap5 -> gap0` triggerは diagnostic candidate / preflight に留める。
- 標準採用はしない。追加未使用月、または2024側の同一family prediction/backtestに固定適用して、再探索なしで崩れないかを見る。
- 次は `gap5` replacement shortの主因である `up_low_vol/ny_overlap`, `range_low_vol/ny_overlap`, `range_low_vol/asia` を、target-monthを見ない prior side drift / realized first-loss / EV calibration で検知できるかを調べる。

## Verification

- `python3 -m py_compile scripts/experiments/short_budget_fixed_rule_audit.py scripts/experiments/short_budget_replacement_trade_audit.py tests/test_short_budget_fixed_rule_audit.py tests/test_short_budget_replacement_trade_audit.py`: OK
- `python3 -m unittest tests.test_short_budget_fixed_rule_audit tests.test_short_budget_replacement_trade_audit tests.test_short_budget_drift_trigger_selection tests.test_short_budget_guard_selection tests.test_docs_reports`: OK, 16 tests
- `git diff --check`: OK
- Fixed trigger artifact generated: OK
- Replacement trade audit artifact generated: OK
