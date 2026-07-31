# Entry EV Side Prior Pressure Fixed 2025 Failure Diagnostics

日時: 2026-07-01 22:29 JST
更新日時: 2026-07-01 22:29 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00244で崩れた `side_prior_pressure_s0p5` fixed 2025-03..12 を、base side-balanced dense720との trade path 差分に分解する `scripts/experiments/entry_ev_side_prior_pressure_failure_diagnostics.py` を追加した。
- q95/floor5 は base `-55.5740` から side-prior `-160.8606` へ悪化。共通entryのexit/score経路差 `-46.6146` と、置換差 `-58.6720` が両方悪い。
- q99/floor5 は base `-229.7382` から side-prior `-177.3790` へ改善。置換差 `+60.6992` が共通entry差 `-8.3400` を上回った。ただし絶対損益はまだNoTrade未満。
- 最悪contextは共通entry側に多く、`long/down_normal_vol/rollover`, `long/range_normal_vol/ny_overlap`, `short/down_normal_vol/ny_overlap` が大きく負けている。
- `range_normal_vol/ny_overlap` などは selected EV-overestimate risk が `0.173913` と低く、現在の `side_prior_pressure` riskだけでは共通損失を検出できない。
- 判断: 診断スクリプトとpath deltaはaccepted。`side_prior_pressure_s0p5` は引き続き標準policyにしない。次はstrength再探索ではなく、共通損失を抑える direction/exit/replacement-aware target へ進む。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_prior_pressure_failure_diagnostics.py`
- Test: `tests/test_entry_ev_side_prior_pressure_failure_diagnostics.py`
- Base fixed trade run:
  - `data/reports/backtests/20260701_131930_20260701_entry_ev_side_balanced_dense720_fixed2025_03_12_trades_s1/`
- Candidate fixed trade run:
  - `data/reports/backtests/20260701_131856_20260701_entry_ev_side_prior_pressure_s0p5_fixed2025_03_12_trades_s1/`
- Diagnostic run:
  - `data/reports/backtests/20260701_132922_20260701_entry_ev_side_prior_pressure_fixed2025_failure_diagnostics_s2/`

## Method

Input predictions:

```text
data/reports/backtests/20260630_232706_20260701_entry_ev_side_prior_pressure_policy_inputs_s1/enriched_predictions/refit2025_predictions_side_prior_pressure.parquet
```

Comparison:

```text
base score = side_balanced_dense_executable
candidate score = side_prior_pressure_s0p5
months = 2025-03..2025-12
profit_multiplier = 1.0
loss_multiplier = 1.2
max_predicted_hold_minutes = 720
```

Trade key:

```text
candidate + month + direction + entry_decision_timestamp
```

Path categories:

| Category | Meaning |
|---|---|
| `common` | baseとcandidateが同じentry side/timestampに入った。ただしexitはvariant別に変わりうる。 |
| `only_base` | baseだけが入ったtrade。 |
| `only_side_prior` | side-priorだけが入ったtrade。 |

`path_delta_summary.csv` では、共通entryのvariant別PnL差と、置換差を分ける。

## Path Delta

| candidate | base total | side-prior total | total delta | common entry delta | replacement delta | base trades | side-prior trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| q95/floor5 | `-55.5740` | `-160.8606` | `-105.2866` | `-46.6146` | `-58.6720` | `132` | `80` |
| q99/floor5 | `-229.7382` | `-177.3790` | `+52.3592` | `-8.3400` | `+60.6992` | `71` | `53` |

Reading:

- q95/floor5は、取引回数が `132 -> 80` に減っても損益が悪化した。単なる低頻度化ではなく、残った共通entryのexit/score経路と新規置換の両方が悪い。
- q99/floor5は、bad replacementを少し改善している。ただし共通entryの損失は残り、total `-177.3790` なので採用圏外。
- したがってs0.5の問題は「入る方向だけ」ではなく、「同じentryをした後のexit/capture」と「置換されたentryの品質」が混在している。

## Worst Month Paths

| candidate | month | path | trades | total | direction error | selected risk |
|---|---|---|---:|---:|---:|---:|
| q95/floor5 | 2025-05 | common | `16` | `-179.0696` | `0.6250` | `0.470070` |
| q99/floor5 | 2025-05 | only_side_prior | `4` | `-178.3440` | `1.0000` | `0.386081` |
| q95/floor5 | 2025-10 | common | `14` | `-127.0328` | `0.4286` | `0.407974` |
| q95/floor5 | 2025-05 | only_side_prior | `7` | `-125.0436` | `0.8571` | `0.422747` |
| q99/floor5 | 2025-12 | common | `12` | `-85.6816` | `0.5000` | `0.367288` |

2025-05はcommonとonly_side_priorの両方で壊れており、単純な置換制御だけでは足りない。

## Worst Contexts

| candidate | path | side | regime | session | trades | total | selected risk | direction error |
|---|---|---|---|---|---:|---:|---:|---:|
| q95/q99 | common | long | down_normal_vol | rollover | `4` | `-120.2736` | `0.650621` | `1.0000` |
| q99 | common | long | range_normal_vol | ny_overlap | `8` | `-117.1300` | `0.173913` | `0.5000` |
| q95/q99 | common | short | down_normal_vol | ny_overlap | `4` | `-110.3328` | `0.486957` | `1.0000` |
| q95 | common | long | range_normal_vol | ny_overlap | `10` | `-94.1700` | `0.173913` | `0.4000` |
| q99 | only_side_prior | short | down_normal_vol | asia | `4` | `-78.2580` | `0.440994` | `0.7500` |

Important:

- `range_normal_vol/ny_overlap` はriskが低いのに大きく負けている。
- `down_normal_vol/rollover` はriskが高く、direction errorも高いので拾える可能性がある。
- `down_normal_vol/ny_overlap` shortはdirection error `1.0` で、side-prior pressureだけではside inversionを止められていない。

## Decision

Accepted:

- Fixed trade path diagnostic script.
- `path_delta_summary.csv` による common-entry delta と replacement delta の分離。
- side/context/risk bucket別の failure diagnosis。

Not accepted:

- `side_prior_pressure_s0p5` as standard policy.
- penalty strengthを同じvalidation/fixed 2025で再探索すること。
- EV-overestimate riskだけで共通損失を止められるという仮定。

Standard policy remains NoTrade.

## Next

1. 共通entry損失を抑えるtargetを作る。候補は `direction_side_inversion`, `exit_capture_failure`, `same_entry_exit_delta`, `realized_loss`。
2. `range_normal_vol/ny_overlap` のような低risk大損contextを、side margin、predicted hold、exit regret、recent realized context lossで説明できるか調べる。
3. 置換entryは `only_side_prior` をtargetにして、replacement quality / positive replacement regret を別に診断する。
4. s0.5は q99 のreplacement改善baselineとして残すが、標準候補ではなく比較対象に留める。
5. 追加chronological component-target windowsを増やし、2025-05/10/12だけに合わせた調整を避ける。

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_prior_pressure_failure_diagnostics.py tests/test_entry_ev_side_prior_pressure_failure_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_prior_pressure_failure_diagnostics`: OK
- Fixed 2025 trade-level diagnostic run: OK
