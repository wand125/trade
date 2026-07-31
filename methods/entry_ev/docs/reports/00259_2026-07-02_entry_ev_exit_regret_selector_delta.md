# Entry EV Exit Regret Selector Delta

日時: 2026-07-02 02:04 JST
更新日時: 2026-07-02 02:04 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00258でpre-registered diagnostic candidateにした `exit_regret_selector_confidenceexit_bucket_t0p4` q99/floor5を、baseline s0.5 q99/floor5とtrade deltaで分解した。
- `entry_ev_quantile_policy_backtest` のrun構造を直接比較する `scripts/experiments/entry_ev_policy_trade_delta_diagnostics.py` を追加した。
- broad deltaでは total delta `+161.2848`。base 70 trades / `-142.3776` から candidate 36 trades / `+18.9072`。
- fixed 2025-03..12 deltaでは total delta `+196.5008`。base 53 trades / `-177.3790` から candidate 21 trades / `+19.1218`。
- 改善の主因はonly-base削除で、broadでは only-base 39 rows / base PnL `-147.4706`、fixed 2025では only-base 36 rows / `-183.5286`。
- ただし勝ちtradeも大きく削っている。broadの removed positive PnL は `+336.7570`、removed negative PnL は `-484.2276`。fixed 2025も removed positive `+300.6870`, removed negative `-484.2156`。
- only-candidate replacementは悪化要因。broadは5 rows / `-25.7298`、fixedは4 rows / `-29.8938`。
- s1 exposure-reduction baselineよりは良い。broad q99/floor5は s1 `-46.3822` / max DD `118.8072` / 28 trades に対し、exit-regret selector `+18.9072` / max DD `54.5368` / 36 trades。
- 判断: delta診断はaccepted。candidateは単なる取引削減より良いが、勝ちtrade削除とreplacement悪化が残る。標準policyにはしない。標準policyはNoTrade。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_policy_trade_delta_diagnostics.py`
- Test:
  - `tests/test_entry_ev_policy_trade_delta_diagnostics.py`
- Broad delta:
  - `data/reports/backtests/20260701_170355_20260702_entry_ev_exit_regret_selector_confexit_t0p4_q99_broad_delta_s2/`
- Fixed 2025 delta:
  - `data/reports/backtests/20260701_170355_20260702_entry_ev_exit_regret_selector_confexit_t0p4_q99_fixed2025_delta_s2/`

## Method

Comparison:

```text
base      = side_prior_pressure_s0p5 q99/floor5
candidate = exit_regret_selector_confidenceexit_bucket_t0p4 q99/floor5
key       = entry_decision_timestamp + direction
```

The delta script reads:

```text
monthly_policy_metrics.csv
trades/<family>/<candidate>/<month>.csv
```

It writes:

```text
trade_delta_rows.csv
group_by_candidate.csv
group_by_candidate_status.csv
group_by_month_candidate.csv
group_by_month_candidate_status_direction.csv
blocking_pairs.csv
stateful_candidate_examples.csv
```

This is the same trade-key logic as the existing `model-trade-delta`, adapted for `entry_ev_quantile_policy_backtest` artifacts.

## Broad Delta

Overall:

| run | trades | adjusted PnL | max DD | max side share |
|---|---:|---:|---:|---:|
| baseline s0.5 q99/floor5 | `70` | `-142.3776` | `162.1992` | `0.6000` |
| exit-regret selector q99/floor5 | `36` | `+18.9072` | `54.5368` | `0.6944` |
| delta | `-34` | `+161.2848` | improved | side concentration worse |

Status decomposition:

| status | rows | base PnL | candidate PnL | delta | removed positive | removed negative | added positive | added negative |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| only_base | `39` | `-147.4706` | `0.0000` | `+147.4706` | `+336.7570` | `-484.2276` | `0.0000` | `0.0000` |
| common | `31` | `+5.0930` | `+44.6370` | `+39.5440` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| only_candidate | `5` | `0.0000` | `-25.7298` | `-25.7298` | `0.0000` | `0.0000` | `+30.2670` | `-55.9968` |

Direction decomposition:

| status | direction | rows | delta | removed positive | removed negative | added positive | added negative |
|---|---|---:|---:|---:|---:|---:|---:|
| only_base | short | `20` | `+109.5770` | `+210.1270` | `-319.7040` | `0.0000` | `0.0000` |
| only_base | long | `19` | `+37.8936` | `+126.6300` | `-164.5236` | `0.0000` | `0.0000` |
| common | long | `23` | `+36.4040` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| common | short | `8` | `+3.1400` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| only_candidate | short | `3` | `-8.0998` | `0.0000` | `0.0000` | `+24.8570` | `-32.9568` |
| only_candidate | long | `2` | `-17.6300` | `0.0000` | `0.0000` | `+5.4100` | `-23.0400` |

Reading:

- Short loss removal is the largest positive component.
- The selector also removes substantial winning shorts and longs.
- Replacement trades are net negative.
- Common trades improve, so the stateful path change is not only a no-trade effect.

## Month Delta

Broad month deltas:

| month | base PnL | candidate PnL | delta | removed positive | removed negative | added negative |
|---|---:|---:|---:|---:|---:|---:|
| 2025-05 | `-162.1992` | `-54.2268` | `+107.9724` | `+63.9300` | `-192.9252` | `-55.9968` |
| 2025-04 | `+16.4640` | `+110.6360` | `+94.1720` | `0.0000` | `-70.1280` | `0.0000` |
| 2025-10 | `-46.6100` | `0.0000` | `+46.6100` | `+26.9500` | `-73.5600` | `0.0000` |
| 2025-06 | `-70.1472` | `-37.3404` | `+32.8068` | `0.0000` | `-32.8068` | `0.0000` |
| 2025-11 | `+60.3910` | `+20.6930` | `-39.6980` | `+94.0270` | `-33.6360` | `0.0000` |
| 2025-09 | `+25.9740` | `-1.5720` | `-27.5460` | `+12.0700` | `-3.8160` | `0.0000` |
| 2025-03 | `-1.7876` | `-28.6080` | `-26.8204` | `+27.2200` | `-0.3996` | `0.0000` |
| 2024-03 | `+24.0400` | `0.0000` | `-24.0400` | `+24.0400` | `0.0000` | `0.0000` |

Reading:

- Improvement is concentrated in 2025-04/05/06/10.
- The selector damages 2024-03, 2025-03, 2025-09, and 2025-11.
- This is not a monotonic monthly improvement; it must pass additional chronology before standardization.

## Fixed 2025 Delta

Fixed 2025-03..12:

| status | rows | base PnL | candidate PnL | delta | removed positive | removed negative | added positive | added negative |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| only_base | `36` | `-183.5286` | `0.0000` | `+183.5286` | `+300.6870` | `-484.2156` | `0.0000` | `0.0000` |
| common | `17` | `+6.1496` | `+49.0156` | `+42.8660` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| only_candidate | `4` | `0.0000` | `-29.8938` | `-29.8938` | `0.0000` | `0.0000` | `+26.1030` | `-55.9968` |

Fixed 2025 direction decomposition:

| status | direction | rows | delta | removed positive | removed negative | added positive | added negative |
|---|---|---:|---:|---:|---:|---:|---:|
| only_base | short | `18` | `+133.6050` | `+186.0870` | `-319.6920` | `0.0000` | `0.0000` |
| only_base | long | `18` | `+49.9236` | `+114.6000` | `-164.5236` | `0.0000` | `0.0000` |
| common | long | `13` | `+39.7260` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| common | short | `4` | `+3.1400` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| only_candidate | short | `2` | `-12.2638` | `0.0000` | `0.0000` | `+20.6930` | `-32.9568` |
| only_candidate | long | `2` | `-17.6300` | `0.0000` | `0.0000` | `+5.4100` | `-23.0400` |

Reading:

- Fixed 2025 improvement is stronger than broad because the removed negative pool is nearly unchanged while removed positive is smaller.
- The same replacement problem remains.
- q99/floor5 remains the only plausible candidate; q95/floor5 was already rejected in 00258.

## s1 Exposure Baseline

Broad q99/floor5:

| run | total PnL | worst role | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| s0.5 baseline | `-142.3776` | `-162.1992` | `70` | `162.1992` | `0.6000` |
| s1 exposure baseline | `-46.3822` | `-57.2272` | `28` | `118.8072` | `0.7143` |
| exit-regret selector t0.4 | `+18.9072` | `-54.2268` | `36` | `54.5368` | `0.6944` |

Reading:

- The selector beats simple s1 exposure reduction on total PnL and max DD.
- Worst role is only slightly better than s1.
- Trade count is higher than s1, so the improvement is not purely fewer entries.
- Side concentration is still high and needs a guard.

## Decision

Accepted:

- Policy-run trade delta diagnostic script for `entry_ev_quantile_policy_backtest` artifacts.
- Broad and fixed q99/floor5 delta diagnostics.
- `exit_regret_selector_confidenceexit_bucket_t0p4` remains a pre-registered diagnostic candidate.

Not accepted:

- Standard-policy promotion.
- Treating the selector as clean loss removal; it removes large winning PnL too.
- Treating the candidate as solved without replacement-risk and side-concentration checks.

Standard policy remains NoTrade.

## Next

1. Run an additional chronology or family replay without changing threshold `0.4`.
2. Add replacement-risk check for the only-candidate rows; current replacement PnL is negative.
3. Add side-concentration constraints or selector-level side share gates before candidate selection.
4. Diagnose why 2025-03/09/11 degrade; those are the main monthly objections.
5. Keep `direction/profit-barrier miss` as a separate modeling lane; this selector is mainly exit-regret/capture.

## Verification

- `python3 -m unittest tests.test_entry_ev_policy_trade_delta_diagnostics`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_policy_trade_delta_diagnostics.py`: OK
- `git diff --check`: OK
- broad q99/floor5 delta run: OK
- fixed 2025 q99/floor5 delta run: OK
