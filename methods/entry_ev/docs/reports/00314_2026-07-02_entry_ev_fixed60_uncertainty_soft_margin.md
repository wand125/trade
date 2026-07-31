# Entry EV Fixed60 Uncertainty Soft Margin

日時: 2026-07-02 18:48 JST
更新日時: 2026-07-02 18:48 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00313の次アクションとして、fixed60 uncertaintyをhard gateではなくentry scoreのsoft marginへ戻した。
- `scripts/experiments/entry_ev_fixed60_uncertainty_margin_policy_inputs.py` を追加し、selected-trade実績から対象月より前だけのfixed60 false-positive priorを作り、prediction parquetのlong/short両側へmargin scoreを生成した。
- 初回実装では新score kindのside-gap quantileを再計算してしまい、w0 no-op controlが baseline `+126.8118` を再現せず `+24.9388` へ崩れた。原因は既存score kindの `preblockgap` side-gap quantileを継承していなかったこと。
- `--side-gap-source-score-kind` を追加し、preblock side-gap quantileを元score kindからコピーすることで、w0 controlは replacement baseline `+126.8118` を再現した。
- raw replacement replayでは、family-aware margin `fixed60_uncertainty_margin_famdirregsess_w5` が `+126.8118 -> +139.1098`、249 tradesへ改善した。ただしmonth floorは `-6.8324` のまま。
- 同branchを00308 pipelineへ戻すと、`isolated_large_loss_long / t-5 / h720 / require-model-used` は total `+338.4078` / month min `-0.8832`。00308同branch `+326.1098` より `+12.2980` 改善した。
- 00310と同じ position-quality overlayを重ねると、`long_range_normal_ny_fixed60_pred_gt0` と `holdext_long_range_normal_ny` は total `+339.2910` / month min `-0.7200`。00310同proxy `+337.6010` より `+1.6900` 改善した。
- ただしstandard admissionは引き続きblocked。default support-awareは `support_aware_only`、support2は `too_many_support_limited_negative_months`、shallow025は `structural_negative_months`。
- 判断: fixed60 uncertainty soft-margin input generationとpreblockgap継承はaccepted infrastructure。family-aware w5 branchはdiagnostic bestを更新。ただし標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_fixed60_uncertainty_margin_policy_inputs.py`
- New tests:
  - `tests/test_entry_ev_fixed60_uncertainty_margin_policy_inputs.py`
- Input generation:
  - `data/reports/backtests/20260702_093605_20260702_entry_ev_00314_fixed60_uncertainty_margin_internal_hgb_preblockgap_s1/`
  - `data/reports/backtests/20260702_094020_20260702_entry_ev_00314_fixed60_uncertainty_margin_hybrid_preblockgap_s1/`
- Replay sweep:
  - `data/reports/backtests/20260702_094120_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_dirregsess_w0_replay_s1/`
  - `data/reports/backtests/20260702_094142_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_dirregsess_w0p5_replay_s1/`
  - `data/reports/backtests/20260702_094204_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_dirregsess_w1_replay_s1/`
  - `data/reports/backtests/20260702_094222_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_dirregsess_w2_replay_s1/`
  - `data/reports/backtests/20260702_094240_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_dirregsess_w5_replay_s1/`
  - `data/reports/backtests/20260702_094258_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_famdirregsess_w0p5_replay_s1/`
  - `data/reports/backtests/20260702_094316_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_famdirregsess_w1_replay_s1/`
  - `data/reports/backtests/20260702_094334_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_famdirregsess_w2_replay_s1/`
  - `data/reports/backtests/20260702_094352_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_famdirregsess_w5_replay_s1/`
- Best branch pipeline:
  - write-trades replay: `data/reports/backtests/20260702_094448_20260702_entry_ev_00314_preblockgap_fixed60_uncertainty_margin_famdirregsess_w5_replay_writetrades_s1/`
  - enrichment: `data/reports/backtests/20260702_094559_20260702_entry_ev_00314_fixed60_margin_w5_enrichment_s1/`
  - isolated exit-capture: `data/reports/backtests/20260702_094616_20260702_entry_ev_00314_fixed60_margin_w5_isolated_exit_capture_s1/`
  - hold target: `data/reports/backtests/20260702_094645_20260702_entry_ev_00314_fixed60_margin_w5_hold_extension_target_s1/`
  - stateful hold-extension: `data/reports/backtests/20260702_094703_20260702_entry_ev_00314_fixed60_margin_w5_hold_extension_stateful_reqmodel_s1/`
  - position-quality overlay: `data/reports/backtests/20260702_094734_20260702_entry_ev_00314_fixed60_margin_w5_position_quality_overlay_s1/`
  - support-aware default/support2/shallow025:
    - `data/reports/backtests/20260702_094821_20260702_entry_ev_00314_fixed60_margin_w5_support_aware_default_s1/`
    - `data/reports/backtests/20260702_094821_20260702_entry_ev_00314_fixed60_margin_w5_support_aware_support2_s1/`
    - `data/reports/backtests/20260702_094821_20260702_entry_ev_00314_fixed60_margin_w5_support_aware_shallow025_s1/`

## Method

Soft margin score:

```text
prior_fp_rate = prior fixed60 false-positive count / prior fixed60 predicted-positive count
uncertainty_input = prior_fp_rate * max(side_fixed60_pred_pnl, 0)
margin_score = base_entry_score - weight * uncertainty_input
```

Prior is built only from selected trades in months earlier than the target month.

Tested context specs:

```text
direction,combined_regime,session_regime
family,direction,combined_regime,session_regime
```

Important compatibility rule:

```text
selected_score quantile: recomputed from margin score
selected_entry_rank quantile: recomputed from selected side
side_gap quantile: copied from original preblockgap source score kind
```

The third line is required because the current benchmark candidate uses `sg95` from a `preblockgap` score kind. Recomputing side gap from the post-margin score changes the gate itself.

## Replay Sweep

Baseline control:

| score kind | total | trades | month min | role min | note |
|---|---:|---:|---:|---:|---|
| w0 preblockgap control | `+126.8118` | `254` | `-6.8324` | `+0.5354` | matches 00307 replacement baseline |
| w0 without preblockgap copy | `+24.9388` | `178` | `-8.6292` | `-7.0900` | invalid comparison |

Margin sweep:

| margin spec | weight | total | trades | month min | reading |
|---|---:|---:|---:|---:|---|
| direction/regime/session | `0.5` | `+125.8898` | `249` | `-6.8324` | slightly worse |
| direction/regime/session | `1` | `+95.6904` | `246` | `-6.8324` | worse |
| direction/regime/session | `2` | `+104.1344` | `244` | `-6.8324` | worse |
| direction/regime/session | `5` | `+107.3444` | `242` | `-6.8324` | worse |
| family/direction/regime/session | `0.5` | `+125.7298` | `252` | `-6.8324` | slightly worse |
| family/direction/regime/session | `1` | `+133.2778` | `251` | `-6.8324` | improves total |
| family/direction/regime/session | `2` | `+137.4178` | `250` | `-6.8324` | improves total |
| family/direction/regime/session | `5` | `+139.1098` | `249` | `-6.8324` | best raw replacement |

Reading:

- Broad direction/regime/session margin suppresses too much useful activity.
- Family-aware margin is sparse but useful: it removes a few low-quality candidates without changing the main raw month floor.
- The raw replacement floor is still an exit/hold-extension problem, so margin alone is not sufficient.

## Hold-Extension Integration

Best raw branch:

```text
fixed60_uncertainty_margin_famdirregsess_w5
-> q95_sg95_rank90_floor5_side_regime_session_month
-> short entry-block side EV penalty replacement
-> isolated_large_loss_long / threshold -5 / fixed720 / require-model-used
```

Stateful hold-extension result:

| branch | total | delta vs raw | trades after extension path | month min | role min |
|---|---:|---:|---:|---:|---:|
| raw replacement w5 | `+139.1098` | `0.0000` | `249` | `-6.8324` | `+0.5354` |
| w5 + holdext `isolated_large_loss_long t-5 h720` | `+338.4078` | `+199.2980` | `241` | `-0.8832` | `+0.5354` |
| 00308 reference same holdext branch | `+326.1098` | n/a | `246` | `-0.8832` | `+0.5354` |

Reading:

- fixed60 uncertainty margin improves the entry candidate set before hold-extension.
- The same hold-extension mechanism then benefits from a better starting path.
- Month floor does not improve versus 00308 until the position-quality overlay is applied.

## Position-Quality Overlay

Best comparable rows:

| entry block rule | total | delta vs input | trades | month min | role min | blocked |
|---|---:|---:|---:|---:|---:|---:|
| none | `+338.4078` | `0.0000` | `241` | `-0.8832` | `+0.5354` | `0` |
| `holdext_long_range_normal_ny` | `+339.2910` | `+0.8832` | `240` | `-0.7200` | `+0.5354` | `1` |
| `long_range_normal_ny_fixed60_pred_gt0` | `+339.2910` | `+0.8832` | `240` | `-0.7200` | `+0.5354` | `1` |
| `long_range_normal_ny_rank_lt0p55` | `+345.7780` | `+7.3702` | `234` | `-0.9430` | `+0.5354` | `7` |
| broad `long_range_normal_ny` | `+343.8510` | `+5.4432` | `233` | `-0.9692` | `+0.5354` | `8` |

Reading:

- Totalだけなら `rank_lt0p55` が最大だが、month floorは `-0.9430` へ悪化する。
- 00310と同じ `long_range_normal_ny_fixed60_pred_gt0` はfloorを `-0.7200` に戻しつつtotalも00310 referenceを上回る。
- blocked countが4件から1件へ減ったため、w5 marginが00310で削っていた悪いcandidateの一部をentry score側で先に処理したと読める。

## Admission

`long_range_normal_ny_fixed60_pred_gt0` / `holdext_long_range_normal_ny`:

| check | status | total | month min | negative months | support-limited neg | shallow neg | structural neg | blocker |
|---|---|---:|---:|---:|---:|---:|---:|---|
| standard | blocked | `+339.2910` | `-0.7200` | `4` | `3` | `1` | `0` | month/role/month-trade/side-share |
| default support-aware | `support_aware_only` | `+339.2910` | `-0.7200` | `4` | `3` | `1` | `0` | none |
| support2 | blocked | `+339.2910` | `-0.7200` | `4` | `3` | `1` | `0` | too many support-limited negative months |
| shallow025 | blocked | `+339.2910` | `-0.7200` | `4` | `3` | `0` | `1` | structural negative months |

Reading:

- 00310と同じfailure typeが残る。
- totalは伸びたが、NoTrade-first standard admissionを通る質にはまだ届かない。
- default support-aware passは診断上の分類であり、標準採用根拠にしない。

## Decision

Accepted:

- fixed60 uncertainty soft-margin prediction-row input generation
- preblockgap side-gap quantile inheritance via `--side-gap-source-score-kind`
- w0 controlを必ず置く運用
- family-aware prior uncertainty margin as diagnostic feature
- w5 branch as new diagnostic best for this replacement + hold-extension lane

Rejected:

- side-gap quantileを再計算したmargin replayをpolicy evidenceとして扱うこと
- direction/regime/session broad marginを標準化すること
- total改善だけでfamily-aware w5を標準policyにすること
- default support-aware passをstandard admissionとして扱うこと

Standard policy remains NoTrade.

## Next

1. w5で消えた/置換されたcandidateを00310 referenceと差分比較し、どのrole/month/contextで改善したか確認する。
2. family-aware uncertainty marginのsupport薄さを、role/familyを過剰に使わない形で再現できるか確認する。
3. `pred_fixed60_uncertainty_prob` headのOOF probabilityをcandidate-row全体へ展開できる形にする。ただしw0 controlとpreblockgap継承を必須にする。
4. standard admissionを通すにはsupport-limited negative monthsとside-shareを直接扱う必要がある。total改善だけを追わない。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_fixed60_uncertainty_margin_policy_inputs.py tests/test_entry_ev_fixed60_uncertainty_margin_policy_inputs.py`: OK
- `uv run python -m unittest tests.test_entry_ev_fixed60_uncertainty_margin_policy_inputs`: OK
- `uv run python -m unittest tests.test_entry_ev_fixed60_uncertainty_margin_policy_inputs tests.test_docs_reports`: OK
- `uv run python -m unittest tests.test_entry_ev_quantile_exit_timing_sensitivity tests.test_entry_ev_stateful_entry_block_overlay tests.test_entry_ev_stateful_support_aware_admission`: OK
- `git diff --check`: OK
- fixed60 uncertainty margin input generation: OK
- invalid no-preblockgap w0 control and corrected preblockgap w0 control: OK
- margin replay sweep: OK
- best w5 write-trades replay: OK
- enrichment / isolated exit-capture / hold-extension target / stateful replay / overlay / support-aware runs: OK
