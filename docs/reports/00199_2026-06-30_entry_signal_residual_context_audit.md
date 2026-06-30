# Entry Signal Residual Context Audit

日時: 2026-06-30 10:51 JST
更新日時: 2026-06-30 10:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00198で prior context signal が拾えなかった `range_low_vol/ny_overlap` replacement shortを、entry-level予測特徴と同月first-loss状態で監査した。
- `short_budget_entry_signal_audit.py` を追加した。同じ `candidate/window/month/combined_regime/session_regime` の過去replacement tradeだけから `prior_context_pnl`, `prior_context_loss_count` を作る。
- current-month first-loss単体は弱い。`gap5/budget0` late 2025-08..12 replacement short `-286.9878` に対し、focus context after first loss は `-37.9120` しか覆えず、`-249.0758` が残る。
- `range_low_vol/ny_overlap` 限定の entry signal `pred_side_confidence_gap <= 0 OR pred_taken_entry_local_rank >= 0.52` は、同contextの `-86.5792` のうち `-80.9316` を覆う。
- 00198の `prior alert OR prior pred-bias` にこのfocus entry signalを足すと、`gap5` late replacement shortの残存は `-94.5582` から `-34.8906` まで縮む。
- これは実行済みreplacement row削除の上限診断であり、dynamic policyではない。次はこの条件をdynamic hookに移し、一玉制約下の再replacementを確認する。

## Artifacts

- Entry signal audit: `data/reports/backtests/20260630_105000_short_budget_entry_signal_audit/`
- Input: `data/reports/backtests/20260630_104800_short_budget_replacement_signal_audit/replacement_signal_rows.csv`

## Method

追加したスクリプト:

- `scripts/experiments/short_budget_entry_signal_audit.py`

For each replacement row, the script adds chronological state within:

```text
candidate + window + month + combined_regime + session_regime
```

The state is based only on earlier rows in that group:

- `prior_context_trade_count`
- `prior_context_pnl`
- `prior_context_loss_count`
- `prior_context_win_count`

The focus context is:

```text
combined_regime = range_low_vol
session_regime = ny_overlap
```

Main tested entry signal:

```text
pred_side_confidence_gap <= 0
OR pred_taken_entry_local_rank >= 0.52
```

The threshold is diagnostic and chosen from the observed residual rows, not yet a validated policy.

## Results

`global_gap5_budget0`, late 2025-08..12:

| condition | covered rows | covered PnL | uncovered rows | uncovered PnL |
|---|---:|---:|---:|---:|
| focus after first loss | `4` | `-37.9120` | `63` | `-249.0758` |
| focus side gap <= 0 | `4` | `-62.4600` | `63` | `-224.5278` |
| focus entry rank >= 0.52 | `3` | `-74.3196` | `64` | `-212.6682` |
| focus side gap <= 0 OR entry rank >= 0.52 | `5` | `-80.9316` | `62` | `-206.0562` |
| prior alert OR pred-bias | `48` | `-192.4296` | `19` | `-94.5582` |
| prior OR focus entry signal | `52` | `-252.0972` | `15` | `-34.8906` |

`global_gap5_budget0`, late 2025-09..12:

| condition | covered rows | covered PnL | uncovered rows | uncovered PnL |
|---|---:|---:|---:|---:|
| focus after first loss | `3` | `-39.9720` | `47` | `-224.3128` |
| focus side gap <= 0 OR entry rank >= 0.52 | `5` | `-80.9316` | `45` | `-183.3532` |
| prior alert OR pred-bias | `38` | `-169.7262` | `12` | `-94.5586` |
| prior OR focus entry signal | `42` | `-229.3938` | `8` | `-34.8910` |

`gap0/budget0` では focus entry signal は実質発火しない。`prior_or_focus_entry_signal` は prior signalと同じで、late 2025-08..12では covered PnL `+9.8220`、late 2025-09..12では `+11.4800`。つまり、このsignalは `gap0` に重ねると良いreplacementも消しやすい。

## Focus Sequence

`global_gap5_budget0`, `range_low_vol/ny_overlap`, late 2025-08..12:

| month | PnL | prior context PnL | side gap | entry rank | signal |
|---|---:|---:|---:|---:|---|
| 2025-08 | `-5.8716` | `0.0000` | `+0.0898` | `0.4928` | false |
| 2025-08 | `+2.0600` | `-5.8716` | `+0.0421` | `0.5011` | false |
| 2025-09 | `-3.0600` | `0.0000` | `-0.0034` | `0.5157` | true |
| 2025-09 | `-3.5520` | `-3.0600` | `-0.0477` | `0.4997` | true |
| 2025-09 | `-1.8360` | `-6.6120` | `+0.1868` | `0.4954` | false |
| 2025-09 | `-34.5840` | `-8.4480` | `-0.0756` | `0.5228` | true |
| 2025-10 | `-18.4716` | `0.0000` | `+0.0479` | `0.5451` | true |
| 2025-12 | `-21.2640` | `0.0000` | `-0.0612` | `0.5695` | true |

first-lossは2025-09後半の大損を拾うが、2025-10/12の初回損失を拾えない。entry-level signalは、初回損失も一部拾えるのが差分。

## Interpretation

- `range_low_vol/ny_overlap` はprior context historyだけでは安全に見える月がある。current-month first-lossも、初回大損を防げない。
- entry-level signalは「shortが選ばれているがside confidence gapが非正、またはentry rankが高すぎる」状態を拾う。これは `range_low_vol/ny_overlap` のreplacement shortに特に効いている。
- 全contextへ広げると過剰削除になり得る。今回のsignalは `range_low_vol/ny_overlap` 専用のpreflightであり、global gateではない。
- `prior OR focus entry signal` は `gap5` branchのreplacement損失上限をかなり削るが、`gap0` branchには不要または有害。dynamic化する場合は `gap5` branch、またはprimary branchだけへ限定する必要がある。

## Decision

- `short_budget_entry_signal_audit.py` は accepted diagnostic infrastructure。
- `range_low_vol/ny_overlap` focused entry signal is a dynamic-policy candidate, not a standard policy.
- Next:
  - `side_context_interaction_guard_apply.py` へ、focus context + entry-level condition のbudget/admission hookを追加する。
  - そのhookを `gap5/budget0` branchまたはprimary branch相当に限定して、再replacement込みでbacktestする。
  - `gap0/budget0` にはこのsignalを重ねない。

## Verification

- `python3 -m py_compile scripts/experiments/short_budget_entry_signal_audit.py tests/test_short_budget_entry_signal_audit.py`: OK
- `python3 -m unittest tests.test_short_budget_entry_signal_audit tests.test_short_budget_replacement_signal_audit tests.test_short_budget_replacement_trade_audit tests.test_short_budget_fixed_rule_audit tests.test_short_budget_drift_trigger_selection tests.test_short_budget_guard_selection tests.test_docs_reports`: OK, 20 tests
- `git diff --check`: OK
- Entry signal audit artifact generated: OK
