# Entry EV Prior OOB Reliability Horizon Choice

日時: 2026-07-03 10:06 JST
更新日時: 2026-07-03 10:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00342の次アクションとして、train support countだけでtail penaltyをgateするのではなく、対象月より前のprediction-vs-actual実績からhead reliabilityを測る列を追加した。
- `delta`, `beats60`, `tail` の各headについて、target monthより前だけを使い、context別に Spearman / AUC / MAE / shrink済みpositive reliability scoreを作る。
- 新score modeとして `pnl_tail_reliability_gated` と `pnl_delta_tail_reliability_gated` を追加した。
- full replay bestでは、`pnl_tail_reliability_gated` と `pnl_delta_tail_reliability_gated` はplain `pnl` と同じ5 tradesを選び、combined `+400.1440` で同点。`pnl_delta_tail` の `+389.5310` よりは良いが、これは新しい優位性ではなく、reliabilityが効かない/弱い局面で悪いdelta-tail補正を実質的に無効化した結果。
- candidate-level horizon choiceでは、`pnl_delta_tail_reliability_gated` が2024-08を `-46.3536 -> -99.7540`、2025-07を `-185.5712 -> -213.0308` に悪化させる。score modeとして標準採用しない。
- 判断: prior/OOB head reliability columnsとprediction artifactsへの出力はaccepted infrastructure。reliability scoreを直接score加点・減点に使う現score modeはpolicy候補としてreject。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Changed tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Run:

- `data/reports/backtests/20260703_010145_20260703_entry_ev_00343_head_reliability_gated_horizon_choice_m1/`

## Method

Reliability target:

```text
delta   : ranker_pred_delta_vs_60      vs horizon_actual_delta_vs_60, Spearman
beats60 : ranker_pred_beats60_prob     vs target_horizon_beats_60, AUC
tail    : ranker_pred_tail_loss_prob   vs target_horizon_tail_loss, AUC
```

Context fallback:

```text
horizon_bucket,row_scope
horizon_bucket
row_scope
global
```

Runtime safety:

- target monthより前のrowsだけを使う。
- actual PnLやactual labelはreliability calibrationの過去実績にのみ使い、target monthの選択には使わない。
- scoreはsupport countでshrinkし、positive reliabilityだけをscore modeへ掛ける。

Experiment setting:

```text
score_modes = pnl,pnl_tail_reliability_gated,pnl_delta_tail_reliability_gated,pnl_delta_tail
min_train_months = 1
min_train_rows = 50
min_head_reliability_rows = 20
min_head_reliability_months = 1
head_reliability_shrinkage_count = 20
max_leaf_nodes = 4
l2_regularization = 5.0
max_iter = 80
```

## Results

### Full Replay

Best scenario by score mode:

| score mode | added | added PnL | combined total | month min | role min | blockers |
|---|---:|---:|---:|---:|---:|---|
| `pnl` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `month_pnl_below_floor,role_trades_low,side_share_high` |
| `pnl_tail_reliability_gated` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | same |
| `pnl_delta_tail_reliability_gated` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | same |
| `pnl_delta_tail` | `5` | `+50.2400` | `+389.5310` | `-0.6120` | `+0.5354` | same |

The reliability-gated best scenarios select the same 5 trades as plain `pnl`:

| role/month/side | horizon | actual |
|---|---:|---:|
| `refit2025_validation 2025-07 short` | `720m` | `+26.4000` |
| `refit2025_validation 2025-08 long` | `720m` | `+12.7200` |
| `refit2025_validation 2025-08 short` | `720m` | `+0.3400` |
| `hybrid2025_0912_external 2025-11 short` | `60m` | `+10.4400` |
| `hybrid2025_0912_external 2025-10 long` | `720m` | `+10.9530` |

`pnl_delta_tail` loses `+10.6130` on the last trade by shortening `hybrid2025_0912_external 2025-10 long` from `720m / +10.9530` to `60m / +0.3400`.

### Target-Level Horizon Choice

Available candidate choices on weak months:

| score mode | 2024-03 | 2024-08 | 2025-07 |
|---|---:|---:|---:|
| `pnl` | `-69.6140` | `-46.3536` | `-185.5712` |
| `pnl_delta_tail` | `-111.0260` | `-46.3536` | `-204.9068` |
| `pnl_tail_reliability_gated` | `-69.6140` | `-46.3536` | `-213.0308` |
| `pnl_delta_tail_reliability_gated` | `-69.6140` | `-99.7540` | `-213.0308` |

Reading:

- 2024-03はprior rowsがないためreliability scoreが0になり、bad tail-aware correctionを避けられる。
- 2024-08はprior reliabilityが `delta +0.3910`, `beats60 +0.5786`, `tail 0.0000` と出るが、この加点はavailable choicesを悪化させる。
- 2025-07は60mのtail reliabilityが `+0.4393`、240mのbeats60 reliabilityが `+0.3647` と出るが、tail/delta reliability scoreは候補全体の実現PnLを悪化させる。

## Interpretation

- Reliability diagnosticsは有用。少なくとも「train support countだけではheadの信頼性を測れない」ことを実データで確認できる。
- ただしpositive reliabilityをそのままscore multiplierにするのは粗い。AUC/Spearmanが正でも、実行PnL上の正しいhorizon選択に直結しない。
- 00343のbestがplain `pnl` と同点なのは改善ではなく、最終gate後に同じ5 tradesへ収束したため。candidate-levelでは悪化月がある。
- 今後はreliabilityをdirect scoreではなく、診断列、admission explanation、head selection、context別confidence、もしくは候補生成不足の優先順位付けに使う。

## Decision

- Prior/OOB head reliability columns: accepted infrastructure.
- Reliability columns in prediction artifacts: accepted.
- `pnl_tail_reliability_gated`: reject as policy.
- `pnl_delta_tail_reliability_gated`: reject as policy.
- Standard policy remains NoTrade.

## Next

1. Reliabilityをdirect score multiplierではなく、head selection / abstention / confidence reportとして使う。
2. 2024-08と2025-07でreliability加点が悪化する理由を、horizon別のranker prediction errorとactual chosen pathで分解する。
3. `fresh2024 2024-11` と `refit2025 2025-03` の候補生成不足を解く方向へ戻る。
4. 00329/00335 low-complexity rankerのplain `pnl` branchをbaselineとして維持する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py tests/test_docs_reports.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00343 prior/OOB reliability replay: OK
