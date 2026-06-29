# Holding Cap Context Walk-Forward

日時: 2026-06-29 20:41 JST
更新日時: 2026-06-29 20:41 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00159` の `range_low_vol:london/rollover` 除外はpost-hoc候補だったため、対象月の結果を見ずにprior月だけで除外contextを選べるか確認した。

direct cap target上では、priorだけで選んだcontext除外により pooled で cap value `+10.6172`、risk0で `+6.6628`、risk5で `+3.9544` の改善余地が出た。一方、実policyへ接続すると、context-walk-forward除外は no-context cap よりtotalが少し低く、post-hoc static pair除外にも届かなかった。

したがって、context-aware holding capは診断featureとしては有効だが、現時点では標準policyへ採用しない。次はよりdenseな `holding_error` / `exit_regret` / `cap_value` 系教師へ寄せる。

## Numbering Audit

ユーザー指示に従い、既存 `docs/reports/*.md` の採番基準を再確認した。

| check | result |
|---|---:|
| existing reports before this report | `167` |
| report files after adding this report | `168` |
| missing `日時` | `0` |
| numbering problems by internal `日時` | `0` |
| first report | `00001_2026-06-28_baseline_backtest_2025-01.md` / `2026-06-28 01:58 JST` |
| latest report | `00168_2026-06-29_holding_cap_context_walkforward.md` / `2026-06-29 20:41 JST` |

採番・最新判断は、引き続きファイル更新時刻や `更新日時` ではなく、ファイル本文の `日時` を基準にする。

## Implementation

追加:

- `scripts/experiments/holding_cap_context_walkforward.py`
  - no-context holding capの `trade_delta_rows.csv` からdirect cap targetを抽出する。
  - `target_month` より前の月だけをpriorとして、cap value mean/sumが負のcontextを除外候補にする。
  - pooled と `case_label` 別の両方で、月別summaryと選択contextを出力する。
- `scripts/experiments/holding_risk_overlay.py`
  - `--exclude-combined-session-pairs-by-month`
  - `--exclude-month-context-selection-scope`
  - `--exclude-month-context-scope`
  - 上記CSVから `target_month, combined_regime, session_regime` を読み、対象月だけcap発火を止める。
- tests
  - `tests/test_holding_cap_context_walkforward.py`
  - `tests/test_holding_risk_overlay.py`

## Direct Target Walk-Forward

入力:

- no-context risk0 delta: `data/reports/backtests/20260629_093003_holding_overlay_no_context_2025_02_08_delta_risk0_month_isolated/`
- no-context risk5 delta: `data/reports/backtests/20260629_093031_holding_overlay_no_context_2025_02_08_delta_risk5_month_isolated/`

条件:

- focus: `short / range_low_vol`
- context: `combined_regime, session_regime`
- selection: `min_prior_support=3`, `min_prior_months=2`, `prior_mean < 0`, `prior_sum < 0`

集計:

| selection scope | scope | months | base cap value | excluded cap value | kept cap value | exclusion delta |
|---|---|---:|---:|---:|---:|---:|
| pooled | pooled | `6` | `16.2708` | `-10.6172` | `26.8880` | `+10.6172` |
| case_label | risk0 | `6` | `6.5752` | `-6.6628` | `13.2380` | `+6.6628` |
| case_label | risk5 | `6` | `9.6956` | `-3.9544` | `13.6500` | `+3.9544` |

月別では `range_low_vol:london` が2025-04以降にprior harmfulとして選ばれ、2025-06では有効だった。一方、2025-05/2025-07では同contextの除外が逆効果になり、2025-08の `asia` 損失はpriorが正だったため検知できなかった。

## Policy Result

2025-02..2025-08、q75/cap60/short-only、評価倍率 `profit=1.0`, `loss=1.2`。

| variant | total pnl | min month pnl | max monthly DD | trades | judgment |
|---|---:|---:|---:|---:|---|
| risk0 baseline | `283.8010` | `-66.1420` | `259.0392` | `761` | baseline |
| risk5 baseline | `270.4024` | `-52.9764` | `224.7524` | `726` | baseline |
| no-context cap risk0 | `378.8870` | `-52.3036` | `145.4232` | `825` | current cap reference |
| no-context cap risk5 | `351.2370` | `-48.5396` | `146.3352` | `790` | current cap reference |
| context-WF exclude risk0 | `376.6688` | `-52.1236` | `145.4232` | `820` | total slightly worse than no-context |
| context-WF exclude risk5 | `348.6384` | `-43.9880` | `146.3352` | `786` | min month improves, total worse |
| post-hoc static pair risk0 | `404.9366` | `-51.3760` | `145.4232` | `810` | not live-valid |
| post-hoc static pair risk5 | `360.9802` | `-43.2404` | `146.3352` | `774` | not live-valid |

context-WFは no-context capに対して、risk0 total `-2.2182`、risk5 total `-2.5986`。risk5のmin monthは `-48.5396 -> -43.9880` と改善するが、利益最大化では不十分。

## Judgment

- post-hocの `range_low_vol:london/rollover` は、prior-onlyでも一部再現する。
- ただしfull policyでは、dynamic prior除外がno-context capをtotalで超えない。
- 2025-08の悪化点は `asia` で、priorではむしろcap有利だったため、sessionだけのcontext ruleでは未来regime変化を拾えない。
- `rollover` はpriorで悪いが、holdoutでsupportが出ない月が多く、静的に入れると複雑さに対して効果が薄い。
- 標準採用はしない。context-WF出力は、holding capの教師設計とregime drift診断へ回す。

## Artifacts

- context walk-forward diagnostics: `data/reports/backtests/20260629_113805_holding_cap_context_wf_range_low_vol_short_2025_02_08/`
- context-WF overlay modeling: `data/reports/modeling/20260629_114030_holding_risk_overlay_short_only_context_wf_excl_2025_02_08/`
- context-WF overlay backtests: `data/reports/backtests/20260629_114030_holding_risk_overlay_short_only_context_wf_excl_2025_02_08/`

## Verification

- `python3 -m unittest tests.test_holding_cap_context_walkforward`: OK, 2 tests
- `python3 -m unittest tests.test_holding_risk_overlay tests.test_holding_cap_context_walkforward`: OK, 3 tests
- `python3 -m py_compile scripts/experiments/holding_risk_overlay.py scripts/experiments/holding_cap_context_walkforward.py`: OK

## Next Actions

- context ruleの採用ではなく、`holding_error_minutes`, `oracle_holding_gap_minutes`, `exit_regret`, `cap_value` をより密な教師として再設計する。
- context-WFのselected contextsはfeature/diagnosticとして残し、hard exclusionではなくrisk calibration側で扱う。
- holding cap系の評価では、totalだけでなくmin month改善が偶然の低頻度除外か、別月でも再現するかを優先確認する。
