# Entry EV Isolated Exit Capture Diagnostics

日時: 2026-07-02 12:32 JST
更新日時: 2026-07-02 12:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00287の次アクションとして、初回/孤立大損と前回勝ち後の大損を exit-capture target として分解した。
- `scripts/experiments/entry_ev_isolated_exit_capture_diagnostics.py` を追加し、enriched tradeに post-exit path、same-side oracle edge、exit-capture failure、oracle hold gap、fixed 60/240/720m のno-replay置換推定を付与した。
- raw `loss_exit30_cd15` benchmarkは266 trades / total `+118.6900` で00286/00287と一致。
- 孤立contextは195 trades / total `+54.8902`。このうち isolated large loss は26件 / `-134.9628`、isolated large-loss capture failureは23件 / `-125.5752`。
- isolated large-loss capture failureのoracle holdは22/23件で実exitより後。つまり「即座に切る」ではなく、捕捉できる場合はhold-extension側の問題が強い。
- ただし fixed horizon 一律置換はpolicyにはならない。`isolated_large_loss_capture_failure -> fixed60` は total `+184.1282` まで伸びるが month min `-22.0794` へ悪化。`first_large_loss -> fixed720` も total `+195.9166` だが month min `-8.9100` でbaseline `-6.8324` より悪い。
- 判断: isolated exit-capture diagnostic infrastructureはaccepted。一律fixed-horizon置換はreject。次は fixed-horizon/hold-extension choice を教師として学習し、stateful selectorでfloorを確認する。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_isolated_exit_capture_diagnostics.py`
- Test:
  - `tests/test_entry_ev_isolated_exit_capture_diagnostics.py`
- Run:
  - `data/reports/backtests/20260702_033140_20260702_entry_ev_isolated_exit_capture_diagnostics_s2/`

## Method

Input enriched trades:

```text
data/reports/backtests/20260702_010625_20260702_entry_ev_raw_cd15_internal_enrichment_s1/residual_enriched_trades.csv
data/reports/backtests/20260702_010637_20260702_entry_ev_raw_cd15_hgb_enrichment_s1/residual_enriched_trades.csv
data/reports/backtests/20260702_010647_20260702_entry_ev_raw_cd15_hybrid_enrichment_s1/residual_enriched_trades.csv
```

Filters:

```text
variant = loss_exit30_cd15
candidate = q95_sg95_rank90_floor5_side_regime_session_month
large_loss_threshold = -2.0
isolated_context = first OR prev_non_loss OR gap > 1440m
exit_capture_failure = same_side_missed_loss OR low_capture OR large_exit_regret
```

Fixed horizon replacement is diagnostic only:

```text
replace flagged trade PnL with actual selected-side fixed 60/240/720m PnL
do not replay replacement entries
do not treat actual fixed horizon as executable prediction
```

## Path Summary

Worst path buckets:

| path | trades | total PnL | large losses | isolated large-loss capture failures | shortfall | oracle after exit |
|---|---:|---:|---:|---:|---:|---:|
| prev_non_loss / >1440 | `51` | `-35.8116` | `9` | `8` | `1159.5246` | `49` |
| first / first | `23` | `-10.3524` | `6` | `6` | `804.2734` | `22` |
| prev_loss / 30-60 | `9` | `-8.7674` | `2` | `0` | `274.2574` | `9` |
| prev_loss / 240-1440 | `28` | `-5.9874` | `6` | `0` | `785.2634` | `25` |
| prev_non_loss / 60-120 | `9` | `-5.2986` | `1` | `1` | `140.2486` | `8` |
| prev_non_loss / 15-30 | `18` | `-5.0556` | `2` | `2` | `574.4326` | `16` |

Reading:

- `prev_non_loss + >1440` and `first` are the main negative isolated buckets.
- Almost all rows have oracle best hold after the actual exit.
- The problem is not simply "more cooldown after loss"; it is "which isolated losses should be allowed to develop rather than being closed by the current signal path."

## Isolated Loss Result

| set | count | PnL | exit regret | shortfall | fixed60 delta | fixed240 delta | fixed720 delta | oracle after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| isolated | `195` | `+54.8902` | `4950.2258` | `4832.2270` | `+62.1092` | `+72.2028` | `+114.2348` | `179` |
| isolated large loss | `26` | `-134.9628` | `784.8158` | `739.7442` | `+52.9738` | `+20.4478` | `+41.4284` | `22` |
| isolated large-loss capture failure | `23` | `-125.5752` | `776.6022` | `739.7442` | `+65.4382` | `+90.3202` | `+135.1724` | `22` |
| first large loss | `6` | `-21.0228` | `196.9068` | `196.9068` | `+5.9028` | `+1.3218` | `+77.2266` | `6` |
| prev_non_loss >1440 large loss | `9` | `-71.1924` | `177.3614` | `139.4594` | `+3.0358` | `-66.8086` | `-181.0036` | `7` |

Reading:

- isolated large-loss capture failureは target として濃い。23件で `-125.5752` を説明し、oracle短期/中期捕捉の余地も大きい。
- しかし最適horizonは一様ではない。`first` は720mがよく見える一方、`prev_non_loss >1440` は240/720mで大きく悪化する。
- よって fixed horizon を直接rule化せず、horizon choice / hold-extension suitability を学習対象にする。

## Replacement Grid

No-replay replacement top rows:

| target | fixed horizon | flagged | delta | total after | month min after |
|---|---:|---:|---:|---:|---:|
| first large loss | `720m` | `6` | `+77.2266` | `+195.9166` | `-8.9100` |
| first large loss | `60m` | `6` | `+5.9028` | `+124.5928` | `-12.1740` |
| first large loss | `240m` | `6` | `+1.3218` | `+120.0118` | `-22.0460` |
| isolated large-loss capture failure | `60m` | `23` | `+65.4382` | `+184.1282` | `-22.0794` |
| isolated large loss | `60m` | `26` | `+52.9738` | `+171.6638` | `-22.0794` |
| isolated loss capture failure | `60m` | `77` | `+101.7566` | `+220.4466` | `-22.9194` |
| isolated large-loss capture failure | `240m` | `23` | `+90.3202` | `+209.0102` | `-49.6074` |
| isolated loss capture failure | `720m` | `77` | `+340.1962` | `+458.8862` | `-111.3074` |

Reading:

- Totalだけなら大きく伸びるが、month floorは全てbaseline `-6.8324` より悪い。
- これはactual fixed horizonを使ったoracle寄り置換であり、それでもfloorが悪化する。
- したがって、固定horizon ruleをそのままpolicy候補にするのは危険。

Worst monthly examples for `isolated_large_loss_capture_failure -> fixed60`:

| role | month | raw PnL | flagged | delta | after |
|---|---|---:|---:|---:|---:|
| refit2025 | 2025-05 | `+2.7726` | `2` | `-24.8520` | `-22.0794` |
| refit2025 | 2025-09 | `-6.8324` | `2` | `-6.5916` | `-13.4240` |
| refit2025 | 2025-03 | `-2.4566` | `1` | `-10.5240` | `-12.9806` |
| hybrid2025_0912 | 2025-12 | `-4.1460` | `1` | `-8.0280` | `-12.1740` |

## Decision

Accepted:

- isolated exit-capture diagnostics
- fixed horizon no-replay replacement grid
- `isolated_context`, `isolated_large_loss`, `isolated_large_loss_capture_failure` as supervised target candidates

Rejected as policy:

- fixed 60/240/720m replacement rules
- using actual fixed horizon deltas as executable evidence
- total-PnL-only rescue of isolated large losses

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark.

## Next

1. Build a supervised hold-extension / horizon-choice target:
   - target rows: isolated large-loss capture failures and nearby isolated losses
   - labels: fixed60/fixed240/fixed720 improvement, best safe horizon, and "do not extend"
   - features: selected side, regime/session, loss-first probability, predicted holding, predicted fixed-horizon PnL, side confidence gap, EV overestimate risk, post-exit bucket
2. Evaluate as a prediction-row feature, not a direct oracle replacement.
3. Replay only after predictions are generated chronologically, then evaluate with 00286 stateful floor selector.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_isolated_exit_capture_diagnostics.py tests/test_entry_ev_isolated_exit_capture_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_isolated_exit_capture_diagnostics`: OK
- isolated exit-capture diagnostics run: OK
