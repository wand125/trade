# Entry EV Hold Extension Stateful Replay

日時: 2026-07-02 12:56 JST
更新日時: 2026-07-02 12:56 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00289の次アクションとして、hold-extension no-replay診断をstateful replayへ接続した。
- `scripts/experiments/entry_ev_hold_extension_stateful_replay.py` を追加し、00289のscored tradesをexit-time extension decision tableとして使い、延長中に重なる後続base tradesをskipする実行経路を作った。
- pre-registered候補 `train_universe=isolated_loss`, apply `isolated_large_loss`, threshold `5.0` はstatefulでも total `+250.7350`, delta vs base `+132.0450` まで改善した。
- ただし month min は `-6.8324` のまま。strict selectorもfloor-only selectorも NoTrade。
- 判断: stateful hold-extension replay infrastructureはaccepted。pre-registered候補は有望なdiagnostic candidateだが、標準policyにはしない。次は2025-09/2025-06のrecall不足を別targetで改善する。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_hold_extension_stateful_replay.py`
- Test:
  - `tests/test_entry_ev_hold_extension_stateful_replay.py`
- Main replay:
  - `data/reports/backtests/20260702_035556_20260702_entry_ev_hold_extension_stateful_replay_isoloss_s2/`
- Strict selector:
  - `data/reports/backtests/20260702_035607_20260702_entry_ev_hold_extension_stateful_selector_isoloss_s1/`
- Floor-only selector:
  - `data/reports/backtests/20260702_035622_20260702_entry_ev_hold_extension_stateful_selector_flooronly_s1/`

## Method

Input:

```text
data/reports/backtests/20260702_034302_20260702_entry_ev_hold_extension_target_model_isoloss_s1/hold_extension_scored_trades.csv
```

Replay rule:

```text
for each source/role/family/variant/candidate/month:
  sort base trades by entry decision time
  if a base trade starts while an extended position is still open:
    skip that base trade
  else:
    if apply_universe is true
       and predicted hold-extension delta >= threshold
       and predicted horizon is after the original exit:
         replace close with actual fixed-horizon close
    else:
         keep the original base trade
```

This is stricter than 00289 no-replay because later trades can be removed by occupancy. It still does not rescore new entries after an altered exit; it is an extension-only stateful path replay. Since extension only lengthens positions, it can remove future base trades but cannot create new trades.

## Stateful Results

| apply universe | threshold | total | delta vs base | month min | role min | extended | skipped | skipped PnL | decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| isolated_large_loss | `5` | `+250.7350` | `+132.0450` | `-6.8324` | `+0.0074` | `7` | `8` | `-3.9820` | diagnostic only |
| isolated_large_loss | `10` | `+145.5146` | `+26.8246` | `-6.8324` | `+0.0074` | `3` | `3` | `+0.3540` | weaker |
| isolated_large_loss_capture_failure | `5` | `+250.7350` | `+132.0450` | `-6.8324` | `+0.0074` | `7` | `8` | `-3.9820` | future label check only |
| isolated_loss | `5` | `+180.0744` | `+61.3844` | `-25.6500` | `+8.3344` | `19` | `23` | `+1.8298` | reject |
| isolated_loss | `10` | `+159.9518` | `+41.2618` | `-15.3530` | `+0.0074` | `6` | `10` | `+2.7244` | reject |

Reading:

- The pre-registered executable diagnostic candidate improves more than no-replay because the skipped overlapping trades are net losing (`-3.9820`).
- Broad `isolated_loss` application still damages floors, matching 00289's warning that high threshold plus narrow exit-observable universe is essential.
- `isolated_large_loss_capture_failure` matches `isolated_large_loss` here, but it remains a future-label diagnostic and is not executable.

## Selector Check

Strict 00286 selector:

```text
best executable candidate:
  isolated_large_loss threshold 5
  total_pnl: +250.7350
  role_total_pnl_min: +0.0074
  month_pnl_min: -6.8324
  blockers: month_pnl_below_floor,role_trades_low,side_share_high
  selected: NoTrade
```

Floor-only selector:

```text
best executable candidate:
  isolated_large_loss threshold 5
  total_pnl: +250.7350
  role_total_pnl_min: +0.0074
  month_pnl_min: -6.8324
  blockers: month_pnl_below_floor
  selected: NoTrade
```

Decision:

- stateful replay does not invalidate the hold-extension signal.
- stateful replay also does not solve the standardization blocker.
- Standard policy remains NoTrade.

## Unfixed Months

Worst executable candidate months for `isolated_large_loss`, threshold `5`:

| source / role | month | after | base | delta | extended | skipped | reading |
|---|---:|---:|---:|---:|---:|---:|---|
| internal refit2025 | 2025-09 | `-6.8324` | `-6.8324` | `0.0000` | `0` | `0` | unflagged |
| internal refit2025 | 2025-06 | `-6.5136` | `-6.5136` | `0.0000` | `0` | `0` | unflagged |
| hybrid 2025-09..12 | 2025-12 | `-4.1460` | `-4.1460` | `0.0000` | `0` | `0` | unflagged |
| internal refit2025 | 2025-12 | `-2.5320` | `+12.9240` | `-15.4560` | `1` | `0` | false positive remains |

Key error pattern:

- 2025-09 has two isolated large-loss long trades with large true extension benefit, but predicted deltas are too small:
  - `-3.4680` PnL, target best delta `+32.3510`, predicted delta `+0.1408`
  - `-2.4324` PnL, target best delta `+6.9124`, predicted delta `+0.9040`
- 2025-06 has a first isolated large-loss long with target best delta `+19.4460`, but predicted delta `+4.8980`, just below threshold.
- hybrid 2025-12 short loss has target best delta `0.0`; extension should not help there.

Reading:

- The remaining blocker is not replay mechanics; it is recall/calibration for specific isolated large-loss long cases.
- Lowering threshold globally is unsafe because 00289/00290 show broad variants damage month floors.
- Next target should separate high-recall long loss-extension from broad isolated-loss extension, probably with regime/session and loss-first context.

## Decision

Accepted:

- stateful hold-extension replay infrastructure
- selector-compatible monthly metric export
- pre-registered candidate as diagnostic line

Rejected:

- standardizing hold-extension threshold 5 without month floor improvement
- broad `isolated_loss` extension
- future-label `isolated_large_loss_capture_failure` as executable evidence

Standard policy remains NoTrade.

## Next

1. Build a high-recall variant for isolated large-loss long trades:
   - target the missed 2025-09/2025-06 cases without lowering threshold globally.
   - include side/regime/session, selected loss-first probability, target horizon class, and model uncertainty.
2. Add a false-positive guard for internal 2025-12 short extension.
3. Re-run stateful extension replay and 00286 selector after the new target.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_hold_extension_stateful_replay.py tests/test_entry_ev_hold_extension_stateful_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_hold_extension_stateful_replay`: OK
- stateful hold-extension replay: OK
- strict 00286 selector: OK
- floor-only 00286 selector: OK
