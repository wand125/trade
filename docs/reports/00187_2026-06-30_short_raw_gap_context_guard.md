# Short Raw Gap Context Guard

日時: 2026-06-30 08:29 JST
更新日時: 2026-06-30 08:29 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `scripts/experiments/side_context_interaction_guard_apply.py` に `signal_short_raw_gap` modeを追加した。
- 目的は `00186` の「selected_side_ruleは狭すぎる」「any_ruleは広すぎる」という反省から、short側だけを直接狙うこと。
- active条件は、最終signalがshortで、penalty前の raw short score gap が閾値以上。
- `context_columns=dataset_month,combined_regime` で dynamic backtest を実行した。
- 全12ヶ月を見た best は `short_gap=5, threshold=20, min_entry_margin=20` で total `+18.5106`。これは初めてNoTradeを上回る形。
- ただし prior-only selection では2025-09..12に大きく負ける。後知恵候補なので標準採用しない。

## Artifacts

- Dynamic sweep: `data/reports/backtests/20260629_232740_short_raw_gap_context_guard_p10_margin10/`
- Prior-only selection min4: `data/reports/backtests/short_raw_gap_context_guard_selection_min4/`
- Prior-only selection min8: `data/reports/backtests/short_raw_gap_context_guard_selection_min8/`

Input source:

- `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10`

## Method

Mode: `signal_short_raw_gap`

An entry decision row is active only when:

```text
final desired signal == short
and raw_short_score - raw_long_score >= short_gap_threshold
```

Then active rows share context:

```text
guarded|dataset_month=<month>|combined_regime=<regime>
```

Inactive rows get unique context, so they do not share drawdown state:

```text
inactive|row=<row>|ts=<timestamp>
```

The backtest still uses one-position constraint, spread/slippage, execution delay, and actual dynamic replacement paths.

## All-Window Sweep

Baseline source run:

- total adjusted PnL `-90.1378`
- worst month `-289.0056`
- max monthly drawdown `289.0056`
- short PnL `-434.3938`
- long PnL `344.2560`
- trades `949`

Top dynamic candidates:

| short gap | threshold | margin | trades | total PnL | worst month | max DD | short PnL | long PnL | active trades | active PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `20` | `20` | `921` | `18.5106` | `-259.3024` | `259.3024` | `-325.7454` | `344.2560` | `379` | `-379.2220` |
| `5` | `20` | `inf` | `921` | `13.4466` | `-259.3024` | `259.3024` | `-330.8094` | `344.2560` | `379` | `-384.2860` |
| `5` | `60` | `20` | `944` | `-42.6168` | `-270.9406` | `270.9406` | `-386.8728` | `344.2560` | `451` | `-396.0922` |
| `0` | `20` | `20` | `898` | `-81.2946` | `-249.2750` | `249.2750` | `-425.5506` | `344.2560` | `420` | `-409.8562` |
| `10` | `40` | `20` | `947` | `-83.9612` | `-276.2330` | `276.2330` | `-428.2172` | `344.2560` | `163` | `-429.0338` |

Best candidate by all-window total:

| month | trades | total PnL | short PnL | long PnL | max DD | active trades | active PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-01 | `92` | `101.4088` | `30.8668` | `70.5420` | `56.3844` | `15` | `30.8668` |
| 2025-02 | `106` | `72.0140` | `41.4892` | `30.5248` | `66.8408` | `50` | `41.5142` |
| 2025-03 | `113` | `29.0862` | `-44.4446` | `73.5308` | `83.3284` | `41` | `-47.5582` |
| 2025-04 | `64` | `169.6110` | `77.4420` | `92.1690` | `113.4036` | `38` | `-41.4600` |
| 2025-05 | `85` | `45.6052` | `91.6122` | `-46.0070` | `71.7846` | `47` | `75.7042` |
| 2025-06 | `84` | `227.2536` | `98.8606` | `128.3930` | `39.1298` | `52` | `95.8606` |
| 2025-07 | `122` | `67.8488` | `64.3040` | `3.5448` | `126.3040` | `29` | `-25.0620` |
| 2025-08 | `98` | `-87.8224` | `-65.7740` | `-22.0484` | `121.8652` | `24` | `-55.7130` |
| 2025-09 | `76` | `-259.3024` | `-246.3304` | `-12.9720` | `259.3024` | `24` | `-176.5734` |
| 2025-10 | `28` | `-30.3682` | `-40.3882` | `10.0200` | `118.3032` | `22` | `-24.4162` |
| 2025-11 | `20` | `-150.6436` | `-173.1826` | `22.5390` | `154.6436` | `14` | `-123.3466` |
| 2025-12 | `33` | `-166.1804` | `-160.2004` | `-5.9800` | `166.1804` | `23` | `-129.0384` |

Interpretation:

- This directly improves short PnL from `-434.3938` to `-325.7454`.
- It also improves worst month and max drawdown versus baseline.
- But 2025-09..12 are still strongly negative; the positive total comes from 2025-01..07.

## Prior-Only Selection

Candidate columns:

```text
short_gap_threshold,
context_drawdown_guard_loss_threshold,
context_drawdown_guard_min_entry_margin
```

### min_train_months=4

| selection | target months | trades | total PnL | worst month | max DD | short PnL | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---|
| worst | `8` | `534` | `-274.9360` | `-249.2750` | `249.2750` | `-352.4254` | `gap0/th20/m20` and `gap5/th20/m20` |
| total/risk_adjusted/risk_budget | `8` | `546` | `-353.6094` | `-259.3024` | `259.3024` | `-431.0988` | `gap5/th20/m20` |

### min_train_months=8

| selection | target months | trades | total PnL | worst month | max DD | short PnL | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---|
| worst | `4` | `145` | `-527.8212` | `-249.2750` | `249.2750` | `-541.4282` | `gap0/th20/m20` |
| total/risk_adjusted/risk_budget | `4` | `157` | `-606.4946` | `-259.3024` | `259.3024` | `-620.1016` | `gap5/th20/m20` |

Prior-only result is a clear failure. The all-window best is not a robust future selector.

## Decision

- Keep `signal_short_raw_gap` as a useful dynamic diagnostic mode.
- Do not promote `gap5/th20/m20` to standard policy despite all-window positive PnL.
- The key lesson is that short raw gap identifies where to intervene, but the threshold selected from earlier months does not survive the 2025-09..12 short regime.
- Next direction:
  - evaluate short bias using a true prior side-drift profile, not raw score gap alone,
  - add a validation gate requiring target-month-independent short-side deterioration evidence,
  - consider a hard monthly/rolling short exposure budget when prior short active PnL is negative.

## Verification

- `python3 -m py_compile scripts/experiments/side_context_interaction_guard_apply.py tests/test_side_context_interaction_guard_apply.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 109 tests
- `git diff --check`: OK
