# Entry EV Support Repair Target Local Confidence

日時: 2026-07-03 09:16 JST
更新日時: 2026-07-03 09:16 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00339の次アクションとして、`fresh2024 2024-03` のfallback/non-model horizon rowsに対し、target-local confidence診断を追加した。
- `scripts/experiments/entry_ev_support_repair_target_local_confidence_diagnostics.py` を追加し、00324 horizon rowsから対象role/month/side/row_scopeを切り出し、観測可能特徴量だけでhorizon別rule surfaceとfeature binsを出すようにした。
- `fresh2024_validation 2024-03 long` のavailable rowsは51 rows / 17 decisions / 3 horizonsで、全て `pred_model_used=false`。60m合計は `-137.9060`、240m合計は `+49.0950`、720m合計は `-99.9060`。既存fallback予測は全horizonで実モデル未使用かつ、240mを高信頼にできていない。
- post-hoc ruleでは `horizon_eq_240` が17 rows / actual sum `+49.0950` / positive 12 / tail loss 1で最上位。`horizon_eq_240 & entry_hour>=15` は3 rows / `+39.1300` / positive 3 / tail 0だが、target-localで極端に薄いのでpolicy evidenceではない。
- `fresh2024_validation 2024-11 long` のgreedy rowは1 decision / 3 horizonsだけ。240mは `+2.4500`、720mは `-5.2800` だが、predictionは240mを選び切れない。これは候補生成不足に加え、horizon confidence不足もあることを示す薄い対照例。
- 判断: target-local confidence diagnosticsはaccepted infrastructure。`fresh03` は方向よりもexit timing / horizon confidence / expected PnL calibrationが弱点。240m固定や時刻ruleは標準policyにしない。次は広いsupport rowsでhorizon-confidence headを作り、target-local ruleは教師/仮説として扱う。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_support_repair_target_local_confidence_diagnostics.py`

Added tests:

- `tests/test_entry_ev_support_repair_target_local_confidence_diagnostics.py`

Runs:

- `data/reports/backtests/20260703_001621_20260703_entry_ev_00340_target_local_confidence_fresh03/`
- `data/reports/backtests/20260703_001621_20260703_entry_ev_00340_target_local_confidence_fresh11/`

Outputs:

```text
target_local_confidence_rows.csv
target_local_confidence_target_summary.csv
target_local_confidence_rule_surface.csv
target_local_confidence_feature_bins.csv
target_local_confidence_examples.csv
config.json
```

## Method

Input is the 00324 support-repair horizon rows:

```text
data/reports/backtests/20260702_201447_20260703_entry_ev_00324_support_repair_target_coverage_00322_s2/support_repair_target_horizon_rows.csv
```

The diagnostic filters by:

```text
role:month:side
row_scope
```

and builds horizon-local rule surfaces from observable fields:

```text
horizon_minutes
entry_hour
side_score
side_margin
score_pct
side_margin_pct
entry_rank_pct
pred_executable_prob
pred_pnl
pred_tail_loss_prob
```

Actual PnL is used only for labels, oracle examples, and evaluation summaries. It is not used as an executable feature or tie-breaker.

## Results

### fresh2024 2024-03 long

Target summary:

| scope | rows | decisions | model-used | fallback | actual sum | positive | tail loss |
|---|---:|---:|---:|---:|---:|---:|---:|
| all horizons | `51` | `17` | `0` | `51` | `-188.7170` | `18` | `29` |
| 60m | `17` | `17` | `0` | `17` | `-137.9060` | `3` | `14` |
| 240m | `17` | `17` | `0` | `17` | `+49.0950` | `12` | `1` |
| 720m | `17` | `17` | `0` | `17` | `-99.9060` | `3` | `14` |

Top post-hoc observable rule surface:

| rule | selected | actual sum | mean | positive | tail loss | reading |
|---|---:|---:|---:|---:|---:|---|
| `horizon_eq_240` | `17` | `+49.0950` | `+2.8879` | `12` | `1` | horizon itself is the main separation |
| `horizon_eq_240__side_margin_ge_0.972091` | `14` | `+46.7270` | `+3.3376` | `10` | `1` | confidence proxy can shrink rows but not enough for policy |
| `horizon_eq_240__entry_rank_pct_ge_0.942857` | `14` | `+37.8650` | `+2.7046` | `9` | `1` | rank proxy is weaker than margin |
| `horizon_eq_240__entry_hour_ge_15` | `3` | `+39.1300` | `+13.0433` | `3` | `0` | very sparse target-local clue, not a rule |

Important reading:

- The profitable 2024-03 candidates are not merely hidden by entry direction. They sit specifically at 240m.
- Existing predictions are constant by horizon and non-model fallback. They do not provide a reliable confidence signal for selecting 240m.
- A target-local time rule can be found, but it is only 3 rows in one month. Treat it as a hypothesis for feature design, not as a policy.

### fresh2024 2024-11 long

Target summary:

| scope | rows | decisions | model-used | actual sum | positive | tail loss |
|---|---:|---:|---:|---:|---:|---:|
| all horizons | `3` | `1` | `3` | `-2.5300` | `2` | `1` |
| 60m | `1` | `1` | `1` | `+0.3000` | `1` | `0` |
| 240m | `1` | `1` | `1` | `+2.4500` | `1` | `0` |
| 720m | `1` | `1` | `1` | `-5.2800` | `0` | `1` |

Top rule is again `horizon_eq_240`, but support is only one decision. This is useful only as a consistency check that horizon choice, not just entry admission, is part of the failure.

## Interpretation

- `fresh2024 2024-03` is a horizon-confidence / calibration problem. The available 240m rows are positive in aggregate, but the model/fallback state cannot distinguish them.
- `fresh2024 2024-11` remains primarily a candidate-generation/support problem, with the same horizon-choice symptom visible in a single row.
- The correct next modeling target is not `long / short / stay_flat` compression. It is a richer target surface: entry quality, horizon-specific executable probability, expected PnL calibration, tail-risk, and support repair utility.
- This supports the earlier design choice to keep multi-head / dense labels. Coarse action labels lose too much information for exit timing and EV calibration.

## Decision

- Target-local confidence diagnostics: accepted infrastructure.
- `horizon_eq_240` / `entry_hour>=15` post-hoc rules: teacher/hypothesis only, not policy.
- Global fallback or fixed 240m policy: reject.
- Standard policy remains NoTrade.

## Next

1. Train a horizon-confidence head across broader support rows, using 00340 target-local rows as diagnostic labels rather than hard-coded rules.
2. Add features that distinguish 240m success from 60m/720m failure without using actual PnL: context prior, session/regime, side margin, entry rank, model-used/fallback state, and calibrated uncertainty.
3. Keep `fresh2024 2024-11` and `refit2025 2025-03` on the candidate-generation track because thin candidate support cannot be solved by reranking alone.
4. Continue to treat actual PnL and fixed-horizon realized outcomes as oracle/teacher/evaluation only.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_target_local_confidence_diagnostics.py tests/test_entry_ev_support_repair_target_local_confidence_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_target_local_confidence_diagnostics`: OK
- fresh03 target-local confidence diagnostics run: OK
- fresh11 target-local confidence diagnostics run: OK
