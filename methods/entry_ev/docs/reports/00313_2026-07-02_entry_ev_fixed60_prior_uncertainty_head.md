# Entry EV Fixed60 Prior Uncertainty Head

日時: 2026-07-02 18:06 JST
更新日時: 2026-07-02 18:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00312のnextとして、`prior_fixed_false_positive_rate`, `prior_fixed_overestimate_mean`, `prior_fixed_uncertainty_pressure` をchronological OOF headへ入れた。
- `scripts/experiments/entry_ev_fixed60_prior_uncertainty_head.py` を追加し、00312 prior rowsから `fixed_false_positive` と `is_loss` を予測する `base` vs `base_fixed_prior` を比較できるようにした。
- target `fixed_false_positive` では、role/familyありのdefault runで AP `0.4642 -> 0.4765`、role/family/group_keyを外したnorole runで AP `0.4616 -> 0.4816`。`prior_fixed_*` は短期path過大評価の識別featureとしては小幅に効いている。
- しかしthreshold / top quantileでhigh-riskを除去するno-replacement診断はPnLに変換されない。default runの `base_fixed_prior` top q95は flagged PnL `+62.0720`、norole runの `base_fixed_prior` top q95も `+7.5910` で、勝ちtradeを削る。
- `is_loss` targetはAUC/APとも弱く、`prior_fixed_*` 追加で一貫した改善は出ない。
- 判断: fixed60 prior uncertainty head infrastructureはaccepted。`prior_fixed_*` はcalibration / uncertaintyの補助featureとして残すが、direct risk threshold / hard gateはreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_fixed60_prior_uncertainty_head.py`
- New test:
  - `tests/test_entry_ev_fixed60_prior_uncertainty_head.py`
- Runs:
  - default categorical features:
    - `data/reports/backtests/20260702_090503_20260702_entry_ev_00313_fixed60_prior_uncertainty_head_s1/`
  - no role/family/group_key categorical features:
    - `data/reports/backtests/20260702_090616_20260702_entry_ev_00313_fixed60_prior_uncertainty_head_norole_s1/`

## Method

Input:

```text
data/reports/backtests/20260702_085053_20260702_entry_ev_00312_fixed60_prior_uncertainty_s1/short_horizon_prior_uncertainty_rows.csv
```

Targets:

```text
fixed_false_positive
is_loss
```

Feature sets:

```text
base:
  fixed_pred_pnl
  selected_fixed_60m_pred_pnl
  selected_fixed_240m_pred_pnl
  selected_fixed_720m_pred_pnl
  selected_loss_first_prob
  pred_side_confidence_gap
  pred_taken_entry_local_rank
  pred_taken_ev
  pred_opposite_ev
  entry_hour

base_fixed_prior:
  base
  + prior_trade_count
  + prior_month_count
  + prior_adjusted_pnl_sum
  + prior_adjusted_pnl_mean
  + prior_adjusted_loss_rate
  + prior_fixed_pred_mean
  + prior_fixed_actual_mean
  + prior_fixed_error_mean
  + prior_fixed_abs_error_mean
  + prior_fixed_overestimate_mean
  + prior_fixed_pred_positive_rate
  + prior_fixed_actual_negative_rate
  + prior_fixed_false_positive_trade_rate
  + prior_fixed_false_positive_rate
  + prior_fixed_uncertainty_pressure
```

Important:

- `fixed_actual_pnl`, `fixed_error`, `fixed_overestimate` are not model features.
- Prior fields are generated from `month < target_month` only.
- The head is chronological by month. It does not train on the target month.

## Score Results

### Default Categorical Features

Categorical features:

```text
source, role, family, direction, combined_regime, session_regime, group_key
```

`fixed_false_positive`:

| group spec | feature set | AUC | AP | Brier |
|---|---|---:|---:|---:|
| `family,direction,combined_regime,session_regime` | `base_fixed_prior` | `0.7824` | `0.4765` | `0.1388` |
| `family,direction,combined_regime,session_regime` | `base` | `0.7851` | `0.4642` | `0.1380` |
| `direction,combined_regime,session_regime` | `base` | `0.7744` | `0.4714` | `0.1407` |
| `direction,combined_regime,session_regime` | `base_fixed_prior` | `0.7661` | `0.4696` | `0.1437` |

Reading:

- Fine contextではAPが `+0.0123` 改善するが、AUC/Brierは改善しない。
- Broader contextではprior追加がむしろ少し悪い。

`is_loss`:

| group spec | feature set | AUC | AP | Brier |
|---|---|---:|---:|---:|
| `family,direction,combined_regime,session_regime` | `base` | `0.4870` | `0.4285` | `0.2887` |
| `family,direction,combined_regime,session_regime` | `base_fixed_prior` | `0.4754` | `0.4234` | `0.2921` |
| `direction,combined_regime,session_regime` | `base_fixed_prior` | `0.4775` | `0.4141` | `0.2978` |
| `direction,combined_regime,session_regime` | `base` | `0.4637` | `0.4087` | `0.2942` |

Reading:

- `is_loss` は分類として弱く、prior追加も安定改善しない。
- fixed60 false-positive targetのほうが、短期path uncertaintyとしては筋が良い。

### No Role / Family / Group Key Check

Categorical features:

```text
direction, combined_regime, session_regime
```

`fixed_false_positive`:

| group spec | feature set | AUC | AP | Brier |
|---|---|---:|---:|---:|
| `family,direction,combined_regime,session_regime` | `base_fixed_prior` | `0.7784` | `0.4816` | `0.1381` |
| `family,direction,combined_regime,session_regime` | `base` | `0.7741` | `0.4616` | `0.1406` |
| `direction,combined_regime,session_regime` | `base` | `0.7741` | `0.4616` | `0.1406` |
| `direction,combined_regime,session_regime` | `base_fixed_prior` | `0.7642` | `0.4598` | `0.1445` |

Reading:

- role/family/group_keyを外しても、fine-context prior featuresはAP `+0.0200`、Brierも改善する。
- したがって `prior_fixed_*` は完全なrole/family記憶だけではない。
- ただしbroader `direction,combined_regime,session_regime` では改善しないため、使えるのはcontext-localなuncertaintyとして限定的。

## Threshold / PnL Results

Default runでPnLが改善したthresholdは2本だけで、どちらも `base` の top q95:

| target | group spec | feature set | threshold | flagged | flagged PnL | delta | target precision |
|---|---|---|---|---:|---:|---:|---:|
| `fixed_false_positive` | `family,direction,combined_regime,session_regime` | `base` | `top_q95` | `13` | `-1.3540` | `+1.3540` | `0.6923` |
| `fixed_false_positive` | `role,direction,combined_regime,session_regime` | `base` | `top_q95` | `13` | `-1.3540` | `+1.3540` | `0.6923` |

`base_fixed_prior` high-risk removal is harmful:

| run | target | group spec | feature set | threshold | flagged | flagged PnL | delta | target precision |
|---|---|---|---|---|---:|---:|---:|---:|
| default | `fixed_false_positive` | `family,direction,combined_regime,session_regime` | `base_fixed_prior` | `top_q95` | `13` | `+62.0720` | `-62.0720` | `0.5385` |
| norole | `fixed_false_positive` | `family,direction,combined_regime,session_regime` | `base_fixed_prior` | `top_q95` | `13` | `+7.5910` | `-7.5910` | `0.5385` |
| norole | `fixed_false_positive` | `family,direction,combined_regime,session_regime` | `base_fixed_prior` | `prob_ge_0.4` | `48` | `+145.4058` | `-145.4058` | `0.5208` |

Reading:

- AP improvement does not imply tradable removal.
- The high predicted fixed60 false-positive rows include profitable rows and compensated paths.
- This is the same pattern seen in 00302/00304: pointwise risk improves target separation somewhat, but direct gate destroys positive path PnL.

## Decision

Accepted:

- chronological fixed60 uncertainty head infrastructure
- `fixed_false_positive` as a better uncertainty target than broad `is_loss`
- `prior_fixed_*` as a context-local feature family
- no-role/family sensitivity check as a required diagnostic when using source-sensitive categorical fields

Rejected:

- direct threshold gate on `pred_fixed60_uncertainty_prob`
- using `is_loss` head as a trade-removal signal
- interpreting AP improvement as policy improvement
- treating `prior_fixed_*` as a standalone hard block

Standard policy remains NoTrade.

## Next

1. Use `pred_fixed60_uncertainty_prob` as a soft calibration / uncertainty margin, not as a binary block.
2. Test whether subtracting an uncertainty penalty from expected PnL improves candidate-level selector outcomes.
3. Keep no-role/family sensitivity alongside any source-aware head to avoid source memorization.
4. Any soft-margin result must go back through stateful replay, role/month floor, side share, and NoTrade-first admission.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_fixed60_prior_uncertainty_head.py tests/test_entry_ev_fixed60_prior_uncertainty_head.py`: OK
- `uv run python -m unittest tests.test_entry_ev_fixed60_prior_uncertainty_head`: OK
- `uv run python -m unittest tests.test_entry_ev_fixed60_prior_uncertainty_head tests.test_entry_ev_short_horizon_prior_uncertainty tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00313 default fixed60 prior uncertainty head run: OK
- 00313 no-role/family sensitivity run: OK
