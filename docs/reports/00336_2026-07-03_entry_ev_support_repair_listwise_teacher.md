# Entry EV Support Repair Listwise Teacher

日時: 2026-07-03 08:28 JST
更新日時: 2026-07-03 08:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00335のleak-free listwise候補面から、actual oracleをpolicyではなくteacherとして扱う診断を追加した。
- `actual_oracle_greedy_selected` を `oracle_teacher_selected` とし、quota groupごとにlearnable groupとsingleton groupを分けた。
- feature別に、observable scoreだけで同じquota/overlap制約下のgreedy選択を行い、teacher overlap、actual PnL、oracle差、rank AUCを比較した。
- baseline bestでは31 rows / 5 groups、learnable 4 groups、singleton 1 group。oracle改善は `+5.7600` だけで、現在の候補面ではmeta-selector教師としてかなり薄い。
- EV -2では111 rows / 6 groups、learnable 5 groups、singleton 1 group。oracle改善は `+25.4430` あるが、`fresh2024_validation 2024-08 long -29.1360` はsingleton negativeで、listwise rerankやmeta-selectorでは救えない。
- 直接feature selectorはどれもcurrentを超えない。repair_scoreはcurrentと同じ、pred PnL系は `-2.5172`、tail/harmful/support proxyは大きく悪化。
- 判断: listwise teacher diagnosticsはaccepted infrastructure。現在の候補面だけで低容量meta-selectorを作るのは薄く、次はsingleton negative向けabstentionとfresh/thin month候補生成を優先する。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_support_repair_listwise_teacher_diagnostics.py`
- Added tests:
  - `tests/test_entry_ev_support_repair_listwise_teacher_diagnostics.py`
- Baseline best teacher diagnostics:
  - `data/reports/backtests/20260702_232826_20260703_entry_ev_00336_support_repair_listwise_teacher_best_s1/`
- EV -2 teacher diagnostics:
  - `data/reports/backtests/20260702_232826_20260703_entry_ev_00336_support_repair_listwise_teacher_evm2_s1/`

Outputs:

```text
support_repair_listwise_teacher_examples.csv
support_repair_listwise_teacher_group_summary.csv
support_repair_listwise_teacher_feature_summary.csv
support_repair_listwise_teacher_overview.csv
config.json
```

## Method

The diagnostic starts from the 00335 leak-free listwise candidate examples:

```text
support_repair_listwise_candidate_examples.csv
```

It treats:

```text
actual_oracle_greedy_selected
```

as a teacher label only. This is not an executable policy signal.

Groups are split into:

```text
learnable group: row_count > quota
singleton group: row_count <= quota
```

Singleton groups are important because no listwise selector can choose a better row inside them. If a singleton is harmful, the required next step is abstention or candidate generation, not reranking.

Observable score probes:

```text
repair_score desc
hv_chosen_score desc
hv_chosen_pred_pnl desc
repair_expected_pnl desc
hv_chosen_pred_executable_prob desc
hv_chosen_pred_tail_loss_prob asc
hv_chosen_pred_harmful_overestimate_prob asc
repair_support_success_proxy desc
hv_chosen_horizon_minutes asc
```

The probes use the same quota and overlap constraints as the listwise diagnostic. `actual_pnl_at_hv_chosen_horizon` is never used outside teacher/oracle summaries.

## Results

Overview:

| scenario | rows | groups | learnable groups | singleton groups | current actual | oracle actual | oracle delta | current losses | singleton negative |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| p0.45 / EV 2 / tail 0.3 | `31` | `5` | `4` | `1` | `+60.8530` | `+66.6130` | `+5.7600` | `0` | `0` |
| p0.45 / EV -2 / tail 0.3 | `111` | `6` | `5` | `1` | `+31.7170` | `+57.1600` | `+25.4430` | `1` | `1` |

Group-level oracle deltas:

| scenario | role | month | side | rows | current | oracle | delta | singleton |
|---|---|---|---|---:|---:|---:|---:|---|
| best | refit2025_validation | 2025-08 | long | `3` | `+12.7200` | `+13.2500` | `+0.5300` | no |
| best | refit2025_validation | 2025-08 | short | `22` | `+0.3400` | `+5.5700` | `+5.2300` | no |
| EV -2 | refit2025_validation | 2025-08 | long | `16` | `+12.7200` | `+13.2500` | `+0.5300` | no |
| EV -2 | refit2025_validation | 2025-08 | short | `72` | `+0.3400` | `+12.3600` | `+12.0200` | no |
| EV -2 | hybrid2025_0912_external | 2025-11 | short | `6` | `+10.4400` | `+23.3330` | `+12.8930` | no |
| EV -2 | fresh2024_validation | 2024-08 | long | `1` | `-29.1360` | `-29.1360` | `0.0000` | yes |

Feature selector summary:

| scenario | selector | actual sum | delta vs current | oracle overlap | oracle AUC | reading |
|---|---|---:|---:|---:|---:|---|
| best | repair_score | `+60.8530` | `0.0000` | `3/5` | `0.5231` | currentと同じ |
| best | pred PnL | `+58.3358` | `-2.5172` | `2/5` | `0.5231` | worsens |
| best | executable prob | `+24.7530` | `-36.1000` | `1/5` | `0.7423` | AUCは高いが選択PnLは悪い |
| best | support proxy | `+25.7830` | `-35.0700` | `2/5` | `0.7192` | direct selectorは悪い |
| EV -2 | repair_score | `+31.7170` | `0.0000` | `3/6` | `0.7460` | currentと同じ |
| EV -2 | pred PnL | `+29.1998` | `-2.5172` | `3/6` | `0.7540` | worsens |
| EV -2 | harmful low | `-40.2810` | `-71.9980` | `2/6` | `0.4976` | reject |
| EV -2 | support proxy | `-0.9390` | `-32.6560` | `1/6` | `0.4667` | reject |

Interpretation:

- Feature AUCだけではstateful PnL改善を意味しない。bestのexecutable probabilityやsupport proxyはteacher AUCが高く見えても、greedy選択にすると大幅に悪化する。
- EV -2のteacher余地は主に `refit2025 2025-08 short` と `hybrid2025 2025-11 short` にある。
- 最大の実務問題である `fresh2024 2024-08 long -29.1360` はsingleton negative。これはcandidate generationかabstentionの問題で、listwise rerankerの教師を増やしても解けない。

## Decision

- `entry_ev_support_repair_listwise_teacher_diagnostics.py`: accepted infrastructure.
- Direct feature selector: reject.
- Low-capacity meta-selector training from the current candidate surface alone: not enough evidence yet.
- Actual oracle labels remain teacher / diagnostic only.
- Standard policy remains NoTrade.

## Next

1. Singleton negative group diagnosticsをabstention layerへ接続する。
2. `fresh2024_validation 2024-08 long` のような唯一候補に対し、support目的だけで入らないためのobservable risk proxyを作る。
3. Learnable groupsのteacherは、同じ候補面を増やしてからchrono/purged targetとして使う。現5-6 groupだけでmeta-selectorを学習しない。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_listwise_teacher_diagnostics.py tests/test_entry_ev_support_repair_listwise_teacher_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_listwise_teacher_diagnostics tests.test_entry_ev_support_repair_listwise_cluster_diagnostics tests.test_entry_ev_support_repair_horizon_replay`: OK
- best / EV -2 teacher diagnostics run: OK
