# Entry EV Row x Horizon Support Repair

日時: 2026-07-03 05:42 JST
更新日時: 2026-07-03 05:42 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00325の次アクションとして、pre-chosen horizonの前に60/240/720mを別候補として評価するrow x horizon support repair replayを実装した。
- `scripts/experiments/entry_ev_support_repair_horizon_replay.py` に `--choice-input-mode row_horizon_grid` を追加し、`broad_horizon_viability_predictions.csv` からthreshold scenario gridを生成できるようにした。
- observable proxyとして `--repair-horizon-penalty-weight` を追加した。scoreは `support_reduction + pred_pnl - tail_prob - weight * horizon/60`。
- actual-floor upper-boundは6本追加、added PnL `+35.3200`、combined total `+374.6110`。00325 upper-bound `+371.6610` から `+2.9500` 改善した。
- pred-only / no horizon penaltyは00325同様にfresh2024 2024-08 long 720m `-29.1360` を拾い、added PnL `+3.2340`、combined `+342.5250` に留まった。
- pred-only / horizon penalty `0.25` はactual-floorなしでfresh2024 2024-08を60m `+2.9500` に切り替え、added PnL `+35.3200`、combined `+374.6110` に到達した。
- ただしhorizon penalty `0.25` は同じrepair set上で見つけた診断値であり、まだpolicy evidenceではない。標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_support_repair_horizon_replay.py`
- Updated tests:
  - `tests/test_entry_ev_support_repair_horizon_replay.py`
- Actual-floor row x horizon replay:
  - `data/reports/backtests/20260702_204031_20260703_entry_ev_00326_row_horizon_support_repair_actualfloor_00322_s2/`
- Pred-only row x horizon replay:
  - `data/reports/backtests/20260702_204031_20260703_entry_ev_00326_row_horizon_support_repair_predonly_00322_s2/`
- Pred-only horizon penalty `0.25`:
  - `data/reports/backtests/20260702_204155_20260703_entry_ev_00326_row_horizon_support_repair_predonly_hpen025_00322_s2/`
- Pred-only horizon penalty `0.5`:
  - `data/reports/backtests/20260702_204155_20260703_entry_ev_00326_row_horizon_support_repair_predonly_hpen050_00322_s2/`
- Pred-only horizon penalty `1.0`:
  - `data/reports/backtests/20260702_204155_20260703_entry_ev_00326_row_horizon_support_repair_predonly_hpen100_00322_s2/`

## Method

New input modes:

```text
chosen
  Existing 00323/00325 behavior. Replay pre-selected hv_chosen_horizon_minutes.

row_horizon
  Expand existing scenario rows into one candidate per horizon.

row_horizon_grid
  Read prediction rows, create threshold scenarios, then expand one candidate per horizon.
```

Repair score:

```text
repair_score =
  support_reduction_value
  + hv_chosen_pred_pnl
  - hv_chosen_pred_tail_loss_prob
  - repair_horizon_penalty_weight * (hv_chosen_horizon_minutes / 60)
```

Main diagnostic settings:

```text
choice_input_mode = row_horizon_grid
selection_mode = repair_score
min_chosen_pred_pnl = 0
max_chosen_tail_prob = 0.3
```

Actual-floor run additionally sets:

```text
min_chosen_actual_pnl = 0
```

The actual-floor run remains an upper-bound / error-analysis diagnostic because it uses future realized PnL.

## Main Results

| run | best scenario | added | added PnL | combined total | month min | role min | remaining extra | remaining hurdle | blockers |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| row x horizon actual-floor | available p0.3 EV-2 tail0.3 model-used | `6` | `+35.3200` | `+374.6110` | `-0.6120` | `+0.5354` | `2` | `+1.4486` | month, side-share |
| row x horizon pred-only | available p0.3 EV-2 tail0.3 model-used | `6` | `+3.2340` | `+342.5250` | `-19.8260` | `-20.8016` | `2` | `+21.2746` | role, month, side-share |
| pred-only hpen0.25 | available p0.4 EV-2 tail0.3 model-used | `6` | `+35.3200` | `+374.6110` | `-0.6120` | `+0.5354` | `2` | `+1.4486` | month, side-share |
| pred-only hpen0.50 | available p0.4 EV-2 tail0.3 model-used | `6` | `+25.4000` | `+364.6910` | `-0.6120` | `+0.5354` | `2` | `+1.4486` | month, side-share |
| pred-only hpen1.00 | available p0.4 EV-2 tail0.3 model-used | `6` | `+17.7840` | `+357.0750` | `-0.6120` | `+0.5354` | `2` | `+1.4486` | month, side-share |

Pred-only hpen0.25 additions:

| role | month | side | decision UTC | horizon | pred PnL | tail | horizon penalty | repair score | actual |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| fresh2024_validation | 2024-08 | long | 2024-08-22 03:39 | 60 | `+0.5880` | `0.0767` | `1.0` | `+1.2613` | `+2.9500` |
| hybrid2025_0912_external | 2025-10 | long | 2025-10-03 00:14 | 720 | `+7.1503` | `0.1520` | `12.0` | `+4.9983` | `+4.7300` |
| hybrid2025_0912_external | 2025-11 | short | 2025-11-10 01:34 | 60 | `+5.0987` | `0.2099` | `1.0` | `+5.6387` | `+9.4100` |
| refit2025_validation | 2025-07 | short | 2025-07-21 06:38 | 240 | `+1.7808` | `0.2601` | `4.0` | `+1.5207` | `+4.6900` |
| refit2025_validation | 2025-08 | short | 2025-08-08 08:27 | 240 | `+2.3763` | `0.2607` | `4.0` | `+2.1157` | `+12.3600` |
| refit2025_validation | 2025-08 | long | 2025-08-14 16:27 | 720 | `+11.1635` | `0.1903` | `12.0` | `+8.9732` | `+1.1800` |

Remaining worst months after hpen0.25:

| role | month | PnL | trades | long | short | side share |
|---|---|---:|---:|---:|---:|---:|
| fresh2024_validation | 2024-11 | `-0.6120` | `1` | `0` | `1` | `1.0000` |
| refit2025_validation | 2025-03 | `-0.4730` | `9` | `5` | `4` | `0.5556` |
| fresh2024_validation | 2024-03 | `-0.3636` | `1` | `0` | `1` | `1.0000` |

## Decision

Accepted:

- row x horizon support repair replay infrastructure
- threshold scenario grid generation from prediction rows
- horizon penalty hook as an observable diagnostic proxy
- hpen0.25 as a follow-up calibration candidate

Rejected:

- treating row x horizon actual-floor as policy evidence
- treating pred-only no-penalty repair_score as policy candidate
- treating hpen0.25 as standard without chronological calibration
- increasing horizon penalty blindly; `0.5` and `1.0` already remove useful long-horizon candidates

Standard policy remains NoTrade.

## Interpretation

The important improvement is specific:

```text
The bad fresh2024 2024-08 720m choice is not unavoidable.
An observable duration penalty can flip that row to the 60m positive path.
```

But this is not yet a robust rule. The same penalty is tuned on the diagnostic repair set, and stronger penalties damage useful 720m/240m choices. The next step is not to lock in `0.25`; it is to learn or calibrate duration risk chronologically.

## Next

1. Build chronological / OOF horizon-duration calibration using only prior months.
2. Compare fixed horizon penalty weights on train-before-validation splits, not on the same repair set.
3. Add horizon duration, tail probability, predicted PnL, and model-used status into a small horizon-choice calibration head.
4. Keep actual PnL floor only as an upper-bound diagnostic.
5. Re-run standard admission gates after any learned duration proxy; current hpen0.25 still fails month floor and side-share.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_horizon_replay.py tests/test_entry_ev_support_repair_horizon_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_horizon_replay`: OK
- 00326 row x horizon actual-floor replay: OK
- 00326 row x horizon pred-only replay: OK
- 00326 horizon penalty sensitivity replays: OK
