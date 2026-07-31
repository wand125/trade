# Entry EV Tail Ceiling Residual Failure Diagnostics

日時: 2026-07-03 13:40 JST
更新日時: 2026-07-03 13:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00355の次アクションとして、既存 `max_chosen_tail_prob=0.3` を通過した後にも残るpositive predicted PnL failureを診断した。
- `entry_ev_tail_ceiling_residual_failure_diagnostics.py` を追加し、00354のno-penalty候補を対象に、tail ceiling通過/遮断のpositive PnL候補をrow-weighted、candidate key、market candidate keyで集計した。
- row-weightedでは、positive predicted PnL 12544 rows / actual PnL `-47285.8192` のうち、tail blocked側は3236 rows / `-47165.1376`。tail pass側は9308 rows / `-120.6816` まで圧縮されていた。
- market candidate dedupでも、positive predicted PnL 205件 / `-1104.5216` に対し、tail blocked側は86件 / `-999.3158`、tail pass側は119件 / `-105.2058`。
- tail ceilingは大きな高tail損失領域をかなり正確に落としている。一方、tail pass後にもlossとwinがほぼ相殺する残存failureが残る。
- 残存failureの単純なhard rule候補は、`pred_pnl_lt_1` / `pred_pnl_lt_2` などが損失捕捉は強いが、勝ち候補も大きく削る。global scalar gateとしては採用しない。
- greedy selectedだけを見ると、tail pass positive rowsは82 rows / `+500.7960`、loss 8 / `-74.3040`、wins `+575.1000`。残存failureの多くはavailable candidates上の低rank/noisy候補で、現selectorがすでにかなり避けている。
- 判断: `max_chosen_tail_prob=0.3` は引き続き維持。次はglobal residual hard gateではなく、selected/near-selected tail-pass residual failureとremaining weak monthsに対象を絞る。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_tail_ceiling_residual_failure_diagnostics.py`

Added tests:

- `tests/test_entry_ev_tail_ceiling_residual_failure_diagnostics.py`

Run:

- `data/reports/backtests/20260703_043840_20260703_entry_ev_00356_tail_ceiling_residual_failure_diagnostics/`

Key outputs:

- `tail_ceiling_residual_overall_summary.csv`
- `tail_ceiling_residual_context_summary.csv`
- `tail_ceiling_residual_rule_summary.csv`
- `tail_ceiling_residual_failure_cases.csv`
- `tail_ceiling_residual_failure_rows.csv`
- `config.json`

## Method

- Candidate scope: 00354 `ranker_replay_candidates_*.csv` 全56本。
- Label filter: `positive_pnl_penalty_label=none`。
- Tail ceiling: `hv_chosen_pred_tail_loss_prob <= 0.3` をpass、`> 0.3` をblocked。
- Focus rows: `predicted_positive_pnl=true` かつ実損益が負の候補。
- Dedup scopes:
  - `row_weighted`
  - `candidate_key`
  - `market_candidate_key`
- Residual rule candidates:
  - harmful probability thresholds
  - predicted PnL low thresholds
  - 720m horizon
  - prior mean/tail/risk
  - residual MAE/bias/overestimate/tail miss
  - model/reliability used flags
  - `positive_bias_and_tail_miss_ge_0p10`

## Results

Overall no-penalty summary:

| scope | positive pred | positive actual PnL | tail pass positive | tail pass PnL | tail pass loss count | tail pass loss rate | tail pass loss PnL | tail pass win PnL | tail blocked positive | tail blocked PnL | blocked loss rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| row-weighted | `12544` | `-47285.8192` | `9308` | `-120.6816` | `4360` | `0.468414` | `-28128.7296` | `+28008.0480` | `3236` | `-47165.1376` | `0.778121` |
| market candidate key | `205` | `-1104.5216` | `119` | `-105.2058` | `62` | `0.521008` | `-380.7048` | `+275.4990` | `86` | `-999.3158` | `0.720930` |

Greedy selected / available candidates comparison:

| row scope | score mode | tail pass positive | tail pass PnL | loss count | loss PnL | win PnL | tail blocked PnL |
|---|---|---:|---:|---:|---:|---:|---:|
| available_candidates | `pnl` | `1092` | `-570.5340` | `544` | `-3504.7680` | `+2934.2340` | `-5445.7926` |
| available_candidates | `pnl_delta_tail_reliability_gated` | `1084` | `-451.9740` | `536` | `-3386.2080` | `+2934.2340` | `-5445.7926` |
| greedy_selected | `pnl` | `82` | `+500.7960` | `8` | `-74.3040` | `+575.1000` | `-503.3208` |
| greedy_selected | `pnl_delta_tail` | `78` | `+482.2360` | `8` | `-74.3040` | `+556.5400` | `-489.2088` |

Residual rule summary on tail-pass positive rows, row-weighted:

| rule | flagged count | flagged actual PnL | failure precision | failure recall | flagged loss PnL | flagged win PnL | kept actual PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `pred_pnl_lt_2` | `5648` | `-16023.0816` | `0.618980` | `0.801835` | `-23220.6336` | `+7197.5520` | `+15902.4000` |
| `pred_pnl_lt_1` | `4216` | `-13109.2736` | `0.719165` | `0.695413` | `-15804.9216` | `+2695.6480` | `+12988.5920` |
| `positive_bias_and_tail_miss_ge_0p10` | `4580` | `-9309.7440` | `0.614847` | `0.645872` | `-18898.1760` | `+9588.4320` | `+9189.0624` |
| `residual_bias_gt_0` | `5484` | `-7930.6144` | `0.573304` | `0.721101` | `-21041.7984` | `+13111.1840` | `+7809.9328` |
| `residual_tail_miss_ge_0p10` | `7940` | `-732.1280` | `0.496222` | `0.903670` | `-24958.2720` | `+24226.1440` | `+611.4464` |
| `harmful_prob_ge_0p50` | `64` | `-70.8864` | `1.000000` | `0.014679` | `-70.8864` | `0.0000` | `-49.7952` |

Weak residual contexts, market candidate dedup:

| role/month/side/context | horizon | tail pass PnL | loss count | loss rate |
|---|---:|---:|---:|---:|
| `refit2025_validation 2025-08 short range_low_vol asia` | `240m` | `-121.7560` | `19` | `0.863636` |
| `refit2025_validation 2025-08 short range_low_vol asia` | `60m` | `-58.2058` | `16` | `0.727273` |
| `refit2025_validation 2025-07 short up_low_vol asia` | `720m` | `-29.1720` | `1` | `1.000000` |
| `fresh2024_validation 2024-08 long down_low_vol asia` | `720m` | `-29.1360` | `1` | `1.000000` |
| `refit2025_validation 2025-08 short range_low_vol asia` | `720m` | `-20.0470` | `9` | `0.409091` |

Worst residual failure examples:

| role/month | side | timestamp UTC | horizon | pred PnL | actual PnL | tail prob | notes |
|---|---|---|---:|---:|---:|---:|---|
| `refit2025_validation 2025-07` | short | `2025-07-21 06:38` | `720m` | `+1.4577` | `-29.1720` | `0.232187` | residual bias `+3.0067`, residual tail miss `0.305430` |
| `fresh2024_validation 2024-08` | long | `2024-08-22 03:39` | `720m` | `+1.2973` | `-29.1360` | `0.167651` | prior mean `-3.4993`, prior tail `0.414536` |
| `refit2025_validation 2025-08` | long | `2025-08-08 10:53` | `60m` | `+0.0133` | `-14.8200` | `0.190789` | harmful prob `0.342284` |
| `refit2025_validation 2025-08` | short | `2025-08-13 00:14` | `720m` | `+2.6273` | `-13.9836` | `0.251053` | range low vol / asia cluster |
| `hybrid2025_0912_external 2025-10` | long | `2025-10-03 00:14` | `240m` | `+0.6115` | `-12.0000` | `0.179848` | up low vol / asia |

## Interpretation

- 00355で見えたcontextual penalty rowsはすべてtail ceilingで落ちていた。00356ではその先を確認し、tail ceilingは高tail・大損領域をほぼ主因として削っていると分かった。
- ただしtail pass後にも、低tailと評価されたpositive predicted PnL候補が損失になる。ここは「方向」だけでなく、expected PnL calibration、horizon choice、exit timing、context driftの複合問題。
- `pred_pnl_lt_1/2` は損失捕捉率が高いが、勝ち候補も削る。勝ち削除を許容するglobal hard gateではなく、calibration featureやselected/near-selected診断に使う。
- `harmful_prob_ge_0p50` はprecisionが高いがsupportが小さすぎる。単体hard gateではほぼno-op。
- available candidates全体では残存failureが大きく見えるが、greedy selectedではtail pass positiveが大きく正で、現selectorが多くの低rank/noisy候補を避けている。次の診断対象は全候補ではなく、selected / near-selected / quota boundary周辺へ絞る。

## Decision

- tail ceiling residual failure diagnostics are accepted infrastructure.
- `max_chosen_tail_prob=0.3` は維持。これを緩める場合は、contextual penaltyとのcounterfactual replayが必須。
- `pred_pnl_lt_1`, `pred_pnl_lt_2`, `positive_bias_and_tail_miss_ge_0p10`, `residual_bias_gt_0` はglobal hard gateとしてはreject。feature / diagnostic signalとして残す。
- 次はselected/near-selected tail-pass residual failureを、quota boundary、remaining weak months、horizon/exit calibrationに分解する。
- 標準policyはNoTrade。

## Next

1. greedy selected / near-selectedだけに絞り、tail pass residual failuresのquota rank、selected boundary、replacement candidateを診断する。
2. `refit2025_validation 2025-08 short range_low_vol asia` clusterを、exit timing / horizon choice / expected PnL calibrationに分解する。
3. `fresh2024 2024-08 long 720m` の低tail大損を、prior mean/tail/riskを使って選択近傍で止められるか再診断する。
4. global residual hard gateではなく、selected/near-selected featureとして `pred_pnl_lt_1/2` と residual bias/tail missを使う。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_tail_ceiling_residual_failure_diagnostics.py tests/test_entry_ev_tail_ceiling_residual_failure_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_tail_ceiling_residual_failure_diagnostics`: OK
- 00356 tail ceiling residual failure diagnostics: OK
