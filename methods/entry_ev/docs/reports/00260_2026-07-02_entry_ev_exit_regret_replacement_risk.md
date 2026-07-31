# Entry EV Exit Regret Replacement Risk

日時: 2026-07-02 02:17 JST
更新日時: 2026-07-02 02:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00259の次アクションとして、exit-regret selectorのonly-candidate replacementを診断した。
- `scripts/experiments/entry_ev_replacement_risk_delta_diagnostics.py` を追加し、trade deltaのonly-candidate rowsをenriched prediction rowsへ戻した。
- targetは `candidate_pnl < 0` ではなく `replacement_stateful_net < 0` とした。理由は、candidate単体が勝っても、より良いbaseline tradeを塞ぐとone-position制約では悪化するため。
- broad all-candidateでは only-candidate 26 rowsの replacement stateful net が `-321.0916`。q99/floor5は5 rows / harmful 3 / candidate PnL `-25.7298` だが、blocked positive `+122.9530` を含めると stateful net `-148.6588`。
- fixed 2025 all-candidateでは only-candidate 24 rowsの replacement stateful net が `-329.4676`。q99/floor5は4 rows / harmful 3 / candidate PnL `-29.8938`, stateful net `-152.8468`。
- `selected_conf_gap_bucket in {strong, nonpositive}` が最も強いscreen。broadでは10 rows / harmful 8 / stateful net `-378.9356`、fixedでも10 rows / harmful 8 / `-378.9356`。非harmのflagged stateful netは `+10.7900`。
- より保守的な `conf_gap_extreme AND profit_barrier_miss` は broad/fixedとも4 rows / harmful 4 / stateful net `-246.6400`。false positiveは0だが、残るharmが大きい。
- 判断: replacement-risk delta diagnosticはaccepted。`conf_gap_extreme` は次のstateful replay candidate。ただし現時点ではpointwise suppression estimateであり、標準policyにはしない。標準policyはNoTrade。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_replacement_risk_delta_diagnostics.py`
- Test:
  - `tests/test_entry_ev_replacement_risk_delta_diagnostics.py`
- Candidate trade enrichment:
  - `data/reports/backtests/20260701_171213_20260702_entry_ev_exit_regret_selector_confexit_t0p4_broad_enrichment_for_replacement_s1/`
- All-candidate broad delta:
  - `data/reports/backtests/20260701_171253_20260702_entry_ev_exit_regret_selector_confexit_t0p4_all_candidates_broad_delta_s1/`
- All-candidate fixed 2025 delta:
  - `data/reports/backtests/20260701_171618_20260702_entry_ev_exit_regret_selector_confexit_t0p4_all_candidates_fixed2025_delta_s1/`
- Broad replacement risk diagnostic:
  - `data/reports/backtests/20260701_171641_20260702_entry_ev_exit_regret_selector_replacement_risk_broad_s1/`
- Fixed 2025 replacement risk diagnostic:
  - `data/reports/backtests/20260701_171641_20260702_entry_ev_exit_regret_selector_replacement_risk_fixed2025_s1/`

## Method

Inputs:

```text
delta rows    = trade_delta_rows.csv from baseline s0.5 vs exit-regret selector t0.4
enriched rows = residual_enriched_trades.csv joined to selector prediction parquet
key           = family + month + candidate + direction + entry_decision_timestamp
```

Targets:

```text
candidate_pnl                 = candidate_adjusted_pnl
replacement_stateful_net       = candidate_stateful_net_adjusted_pnl
replacement_harm_target        = replacement_stateful_net < 0
direct_loss_target             = candidate_pnl < 0
positive_blocking_harm_target  = blocked positive baseline PnL > 0 and replacement_stateful_net < 0
positive_replacement_regret    = blocked positive baseline PnL - candidate_pnl
```

The important distinction is:

```text
candidate PnL can be positive
but replacement stateful net can be negative
if the candidate blocks a better baseline trade.
```

This happened in the 2025-11 short replacement.

## Broad Replacement Rows

Broad all-candidate only-candidate rows:

| candidate | rows | harmful | direct losses | positive blocking harm | candidate PnL | stateful net | blocked positive | positive replacement regret |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| q95/floor5 | `21` | `9` | `11` | `1` | `-120.4826` | `-172.4328` | `+122.9530` | `+243.4356` |
| q99/floor5 | `5` | `3` | `2` | `1` | `-25.7298` | `-148.6588` | `+122.9530` | `+148.6828` |

Reading:

- q99/floor5 only-candidate looked mildly negative by direct PnL, but is much worse under one-position stateful value.
- The replacement problem is not just bad added trades; it also includes blocking better baseline trades.
- q95/floor5 has more replacement support but the same structural problem.

## Screen Diagnostics

Broad screen summary:

| screen | flagged rows | harmful | direct losses | positive blocking harm | flagged PnL | flagged stateful net | flagged nonharm net | kept stateful net |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| conf_gap_extreme | `10` | `8` | `6` | `2` | `-133.0296` | `-378.9356` | `+10.7900` | `+57.8440` |
| conf_gap_extreme_or_global_source | `11` | `8` | `6` | `2` | `-131.2496` | `-376.7560` | `+12.9696` | `+55.6644` |
| conf_gap_strong | `9` | `7` | `5` | `2` | `-109.9896` | `-355.8956` | `+10.7900` | `+34.8040` |
| conf_gap_extreme_and_profit_miss | `4` | `4` | `2` | `2` | `-0.7340` | `-246.6400` | `0.0000` | `-74.4516` |
| profit_barrier_miss | `17` | `8` | `9` | `2` | `-28.2668` | `-203.1460` | `+86.1264` | `-117.9456` |
| exit_regret_global_source | `5` | `3` | `3` | `0` | `-67.8936` | `-67.4940` | `+3.5796` | `-253.5976` |

Fixed 2025 screen summary is nearly identical for the main screen:

| screen | flagged rows | harmful | flagged stateful net | flagged nonharm net | kept stateful net |
|---|---:|---:|---:|---:|---:|
| conf_gap_extreme | `10` | `8` | `-378.9356` | `+10.7900` | `+49.4680` |
| conf_gap_extreme_and_profit_miss | `4` | `4` | `-246.6400` | `0.0000` | `-82.8276` |

Reading:

- `conf_gap_extreme` catches the largest replacement harm with small false-positive stateful value.
- `profit_barrier_miss` is too broad; it flags many rows and still leaves large harm.
- `exit_regret_global_source` catches no-prior replacements but misses most bucket-supported harm.
- `conf_gap_extreme_and_profit_miss` is clean but too conservative.

## Candidate Conf-Gap Detail

Broad candidate/conf-gap:

| candidate | conf gap | rows | harmful | candidate PnL | stateful net | blocked positive |
|---|---|---:|---:|---:|---:|---:|
| q95/floor5 | strong | `7` | `5` | `-97.7258` | `-220.6788` | `+122.9530` |
| q99/floor5 | strong | `2` | `2` | `-12.2638` | `-135.2168` | `+122.9530` |
| q99/floor5 | nonpositive | `1` | `1` | `-23.0400` | `-23.0400` | `0.0000` |
| q95/floor5 | weak | `8` | `2` | `+7.2136` | `+50.4724` | `0.0000` |
| q99/floor5 | weak | `1` | `0` | `+5.4100` | `+5.4100` | `0.0000` |

Reading:

- The q99/floor5 harmful replacement rows are fully covered by `strong` or `nonpositive`.
- Weak bucket is not a blocker here; it is net positive.
- Medium bucket is mixed and should not be blocked directly.

## Decision

Accepted:

- Replacement-risk delta diagnostic infrastructure.
- `replacement_stateful_net` as the correct target for one-position replacement harm.
- `selected_conf_gap_bucket in {strong, nonpositive}` as the next pre-registered replacement guard candidate for stateful replay.

Not accepted:

- Treating pointwise suppression estimates as policy evidence.
- Blocking replacement rows directly without rerunning the one-position stateful policy.
- Promoting `conf_gap_extreme` to standard policy before additional chronology / family replay.

Standard policy remains NoTrade.

## Next

1. Add a selector-level replacement guard using `conf_gap_extreme`, keeping exit-regret threshold `t0.4` unchanged.
2. Replay statefully on broad and fixed 2025, then compare against 00258/00259 candidate and s1 exposure baseline.
3. If stateful replay improves, pre-register the guard and run additional chronology or family replay without retuning.
4. Keep `conf_gap_extreme_and_profit_miss` as a conservative fallback screen, but do not choose between them by same-window total PnL.

## Verification

- `python3 -m unittest tests.test_entry_ev_replacement_risk_delta_diagnostics tests.test_entry_ev_policy_trade_delta_diagnostics tests.test_docs_reports`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_replacement_risk_delta_diagnostics.py scripts/experiments/entry_ev_policy_trade_delta_diagnostics.py`: OK
- broad all-candidate delta run: OK
- fixed 2025 all-candidate delta run: OK
- broad replacement-risk diagnostic run: OK
- fixed 2025 replacement-risk diagnostic run: OK
