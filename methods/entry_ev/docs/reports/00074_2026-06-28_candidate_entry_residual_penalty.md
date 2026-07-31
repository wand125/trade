# Candidate Entry Residual Penalty

日時: 2026-06-28 23:11 JST
更新日時: 2026-06-28 23:11 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回の all-row `regime residual penalty` は、row-levelの予測過大評価を削っても、実際にentryするtrade集合の壊れ方を表せず、2024-12 fixed holdoutを大きく悪化させた。

今回は、residual fit対象を「entry条件を通った候補行」だけに限定する `candidate-entry residual penalty` を追加した。

目的:

- 全rowの残差ではなく、実際のpolicyが選びやすい行の過大評価を見る。
- side別entry threshold、short offset、side margin、entry local rankをfit対象の条件へ反映する。
- post-hocなmanual ruleではなく、OOF residualから自動で壊れやすいside/sessionを削る。

結論:

- 実装は残す。
- `session_regime`, weight `1`, min rank `0.5` は2024-12を raw hybrid baseline `-54.6032` から `-17.1780` へ縮めた。
- ただしvalidation 4foldの min adjusted pnlは `50.5324` で、既存hybrid baseline `81.5352`、`long:ny_late:15` side EV penalty候補 `85.7834` / `93.8904` より弱い。
- 2025-02も baseline `+81.8334` より `+78.0748` へやや低下した。
- 標準policyには採用しない。candidate-entry residualは診断・探索軸として残し、次は「選ばれたtradeの realized failure」または「one-position制約込みの実行trade residual」を学習対象にする。

## Implementation

`ResidualPenaltyConfig` に candidate-entry fit条件を追加した。

- `candidate_entry_only`
- `entry_threshold`
- `long_entry_threshold_offset`
- `short_entry_threshold_offset`
- `side_margin`
- `min_entry_rank`
- `long_entry_rank_column`
- `short_entry_rank_column`

追加関数:

- `candidate_entry_side_masks`

fit対象:

```text
long candidate:
  long_score >= short_score
  long_score > entry_threshold + long offset
  abs(long_score - short_score) >= side_margin
  long_entry_rank >= min_entry_rank

short candidate:
  short_score > long_score
  short_score > entry_threshold + short offset
  abs(long_score - short_score) >= side_margin
  short_entry_rank >= min_entry_rank
```

`oof-residual-penalty` CLIにも同じ引数を追加した。

## Setup

Input:

- OOF predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- 2024-12 predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- 2025-02 predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2025_02.parquet`

Policy / fit filter:

- group columns: `session_regime`
- validation months: `2024-07,2024-09,2024-11,2025-01`
- `entry_threshold=15`
- `short_entry_threshold_offset=4`
- `side_margin=5`
- `min_entry_rank=0.5`
- `min_group_size=50`
- `prior_strength=200`
- evaluation: profit `1.0`, loss `1.20`

Candidate support in final calibrator:

| side | candidate rows | side overestimate mean |
|---|---:|---:|
| long | `2326` | `4.5327` |
| short | `6285` | `9.2177` |

Top raw excess by session:

| side | group | n | group overestimate | raw excess vs side |
|---|---|---:|---:|---:|
| long | `asia` | `140` | `5.5551` | `1.0225` |
| long | `ny_late` | `1277` | `5.3192` | `0.7865` |
| short | `rollover` | `180` | `10.3976` | `1.1799` |
| short | `london` | `3830` | `9.9739` | `0.7561` |

## Diagnostics

weight `10` は過剰に削りすぎた。

| split | selected rows raw | selected rows penalized | selected avg raw | selected avg penalized | side acc raw | side acc penalized |
|---|---:|---:|---:|---:|---:|---:|
| validation OOF | `54967` | `32242` | `19.0855` | `17.7061` | `0.5449` | `0.5016` |
| 2024-12 apply | `14438` | `8919` | `12.4549` | `13.8844` | `0.3441` | `0.3900` |
| 2025-02 apply | `21819` | `14302` | `18.2948` | `18.5735` | `0.4376` | `0.4508` |

2024-12/2025-02のrow-level apply品質は改善するが、validation OOF品質を大きく壊すため候補から外した。

weight `1` は弱い減点として比較対象にした。

| split | selected rows raw | selected rows penalized | selected avg raw | selected avg penalized | side acc raw | side acc penalized |
|---|---:|---:|---:|---:|---:|---:|
| validation OOF | `54967` | `47193` | `19.0855` | `19.1005` | `0.5449` | `0.5427` |
| 2024-12 apply | `14438` | `12593` | `12.4549` | `13.2716` | `0.3441` | `0.3623` |
| 2025-02 apply | `21819` | `19643` | `18.2948` | `18.8410` | `0.4376` | `0.4527` |

row-levelでは小幅改善だが、validation OOFのside accuracyはわずかに落ちる。entry候補だけに絞っても、row-level selected avgと実行売買PnLはまだ一致しない。

## Backtest Results

`session_regime`, weight `1`, min rank `0.5`, validation 4fold:

| min entry rank | fold count | eligible folds | min adjusted pnl | sum adjusted pnl | min trades | max DD | forced exit max | eligible |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `0.5` | `4` | `4` | `50.5324` | `412.1412` | `22` | `56.0916` | `0.0000` | true |
| `0.0` | `4` | `4` | `45.3760` | `392.4874` | `22` | `66.1056` | `0.0000` | true |

Fixed holdout:

| month | min entry rank | adjusted pnl | raw pnl | trades | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | `0.5` | `-17.1780` | `+10.5310` | `45` | `0.8967` | `86.6362` | `0` |
| 2024-12 | `0.0` | `-35.5632` | `-4.3530` | `43` | `0.8101` | `94.9576` | `0` |
| 2025-02 | `0.5` | `+78.0748` | `+117.7910` | `119` | `1.3276` | `95.0580` | `0` |
| 2025-02 | `0.0` | `-8.6654` | `+39.7760` | `108` | `0.9702` | `116.6944` | `0` |

比較:

- raw hybrid baseline: validation min `81.5352`, 2024-12 `-54.6032`, 2025-02 `+81.8334`
- `long:ny_late:15` risk top: validation min `85.7834`, 2024-12 `-5.4938`, 2025-02 `+79.4018`
- candidate residual w1 rank0.5: validation min `50.5324`, 2024-12 `-17.1780`, 2025-02 `+78.0748`

candidate residualは2024-12の損失を縮めるが、validation robustnessが大きく弱く、既存候補の台地に届かない。

## Decision

- candidate-entry residual penaltyの実装とCLIは残す。
- weight `10` はvalidation OOFを壊すため採用しない。
- weight `1`, rank `0.5` は2024-12を改善するが、validation min pnlが弱いため標準policyへ昇格しない。
- all-row residualよりは実行候補に近いが、まだ「1玉制約で実際に選ばれたtrade」の損益を直接見ていない。
- 次は candidate-row residual のgroup平均ではなく、policy実行後の selected trade realized residual / side failure / exit regret を、OOFかwalk-forwardで学習・校正する。

## Artifacts

- w10 2024-12 apply: `data/reports/modeling/20260628_140745_candidate_residual_session_w10_rank05_2024_12/`
- w10 2025-02 apply: `data/reports/modeling/20260628_140745_candidate_residual_session_w10_rank05_2025_02/`
- w1 2024-12 apply: `data/reports/modeling/20260628_140817_candidate_residual_session_w1_rank05_2024_12/`
- w1 2025-02 apply: `data/reports/modeling/20260628_140817_candidate_residual_session_w1_rank05_2025_02/`
- validation sweeps: `data/reports/backtests/candidate_residual_session_w1_rank05_validation_base/`
- validation summary: `data/reports/backtests/candidate_residual_session_w1_rank05_validation_summary/20260628_140901_model_sweep_summary/`
- fixed tests: `data/reports/backtests/candidate_residual_session_w1_rank05_fixed_tests/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `PYTHONPATH=src python3 -m unittest tests.test_backtest`
- `git diff --check`
