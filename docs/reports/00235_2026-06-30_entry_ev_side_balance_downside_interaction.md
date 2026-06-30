# Entry EV Side Balance Downside Interaction

日時: 2026-06-30 19:22 JST
更新日時: 2026-06-30 19:22 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00234の次アクションとして、side-balance drift単体ではなく、対象月より前の同一 `direction + combined_regime + session_regime` のdownside evidenceとの相互作用を診断する `scripts/experiments/entry_ev_side_balance_downside_interaction.py` を追加した。
- prior evidenceは `prior_loss_rate`, `prior_direction_error_rate`, `prior_large_exit_regret_rate`, `prior_avg_adjusted_pnl` を低容量に合成し、`prior_downside_risk_score` と `side_balance_downside_interaction_score = abs(side_balance_signed_drift_for_trade) * prior_downside_risk_score` を作る。
- q99 floor5では `prior_downside_risk_score >= 0.20` が 7 trades / `-31.1784` を拾い、pointwise kept totalを `-10.2286 -> +20.9498` へ改善した。
- ただし kept min role は `-30.9390`、kept min month は `-33.4920` のままで、NoTrade-first gateは通らない。
- q95 floor5では best-looking screenでも kept min role `-74.8268` や `-42.7904` が残り、fresh tailを救えない。
- 最大損失の `fresh2024 2024-04 long range_low_vol/london -33.4920` は prior supportが0で risk/intersection scoreが0。`fresh2024 2024-03 short range_low_vol/london -32.0364` はrisk高だが driftが `0.0131` と小さく、interactionだけでは弱い。
- 判断: side-balance x downside interaction diagnosticsはaccepted。hard gate / direct penaltyとしては採用しない。prior downsideはside-balanceの補助特徴、selector/ranking特徴、downside-weighted dense target候補に留める。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_balance_downside_interaction.py`
- Test: `tests/test_entry_ev_side_balance_downside_interaction.py`
- Input enriched trades:
  - `data/reports/backtests/20260630_100834_20260630_entry_ev_side_balance_feature_diagnostics_s1_clean/enriched_side_balance_trades.csv`
- Diagnostics:
  - `data/reports/backtests/20260630_101914_20260630_entry_ev_side_balance_downside_interaction_s1/`

## Method

Prior stats are built with only months earlier than the target month:

```text
context = direction + combined_regime + session_regime
prior months < target month
```

Risk score:

```text
support_weight = clip(prior_trade_count / 5, 0, 1)
pnl_risk = clip(-prior_avg_adjusted_pnl / 20, 0, 1)

prior_downside_risk_score =
  support_weight * (
    0.30 * prior_loss_rate
    + 0.25 * prior_direction_error_rate
    + 0.25 * prior_large_exit_regret_rate
    + 0.20 * pnl_risk
  )

side_balance_downside_interaction_score =
  abs(side_balance_signed_drift_for_trade) * prior_downside_risk_score
```

Screen effects are still pointwise diagnostics only. They remove flagged selected trades from the realized path and do not simulate one-position replacement trades.

## Role Summary

| role | candidate | trades | total | min trade | risk mean | interaction mean | abs drift mean |
|---|---|---:|---:|---:|---:|---:|---:|
| fresh2024 | q95 floor5 | `8` | `-82.2428` | `-33.4920` | `0.2003` | `0.0127` | `0.0644` |
| fresh2024 | q99 floor5 | `6` | `-38.3550` | `-33.4920` | `0.2082` | `0.0162` | `0.0816` |
| cal2024 | q95 floor10 | `21` | `-11.2600` | `-18.9120` | `0.0000` | `0.0000` | `0.0087` |
| refit2025 | q99 floor10 | `1` | `-7.3764` | `-7.3764` | `0.2000` | `0.0127` | `0.0637` |
| cal2024 | q99 floor5 | `13` | `-2.1072` | `-8.5920` | `0.0077` | `0.0014` | `0.0648` |
| cal2024 | q95 floor5 | `26` | `+2.8654` | `-15.7200` | `0.0115` | `0.0021` | `0.0462` |
| cal2024 | q99 floor10 | `9` | `+8.5684` | `-2.0676` | `0.0000` | `0.0000` | `0.0203` |
| refit2025 | q95 floor10 | `2` | `+26.8336` | `-7.3764` | `0.4273` | `0.0174` | `0.0487` |
| refit2025 | q99 floor5 | `10` | `+30.2336` | `-14.2800` | `0.1414` | `0.0155` | `0.1024` |
| refit2025 | q95 floor5 | `19` | `+93.9912` | `-15.1524` | `0.2324` | `0.0247` | `0.0973` |

Important observation: refit winning candidates also have high risk mean and interaction mean. High prior downside interaction is not automatically bad; it sometimes appears in profitable recovered contexts.

## Pointwise Screens

Best-looking rows:

| candidate | screen | risk thr | drift thr | removed trades | removed pnl | kept total | kept min role | kept min month | delta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| q99 floor5 | risk_only | `0.20` | n/a | `7` | `-31.1784` | `+20.9498` | `-30.9390` | `-33.4920` | `+31.1784` |
| q99 floor5 | risk_and_abs_drift | `0.20` | `0.02` | `7` | `-31.1784` | `+20.9498` | `-30.9390` | `-33.4920` | `+31.1784` |
| q95 floor5 | risk_and_underrepresented | `0.20` | `0.02` | `9` | `-11.7604` | `+26.3742` | `-74.8268` | `-41.3348` | `+11.7604` |
| q95 floor5 | risk_only | `0.20` | n/a | `14` | `-9.6268` | `+24.2406` | `-42.7904` | `-33.4920` | `+9.6268` |
| q99 floor10 | risk_only / interaction | `0.05..0.20` | `0.02..0.10` | `1` | `-7.3764` | `+8.5684` | `+8.5684` | `-1.8000` | `+7.3764` |

The q99 floor5 improvement is real as a pointwise diagnostic, but it does not remove the largest fresh loss and does not make role/month floors non-negative. q99 floor10 can make role totals positive after removing one loss, but the monthly floor and support remain too thin.

## Worst Buckets

| candidate | risk bucket | interaction bucket | trades | total | abs drift mean | taken penalty |
|---|---|---:|---:|---:|---:|---:|
| q95 floor5 | `0p25_0p50` | `0_0p005` | `1` | `-32.0364` | `0.0131` | `0.0131` |
| q95 floor5 | `0p10_0p25` | `0p02_0p05` | `1` | `-14.2800` | `0.1761` | `0.1761` |
| q99 floor5 | `0p10_0p25` | `0p02_0p05` | `1` | `-14.2800` | `0.1761` | `0.1761` |
| q95 floor10 | `none` | `none` | `21` | `-11.2600` | `0.0087` | `0.0087` |
| q95 floor5 | `0p10_0p25` | `0p005_0p02` | `2` | `-9.5244` | `0.0496` | `0.0000` |
| q99 floor5 | `0p10_0p25` | `0p005_0p02` | `2` | `-9.5244` | `0.0496` | `0.0000` |

The worst bucket is high prior risk but low side-balance drift. This means multiplying risk by drift hides an important class of loss. Conversely, some high-risk/high-interaction buckets are positive, so risk-only hard blocking is also unsafe.

## Decision

Accepted:

- `prior_downside_risk_score` as a diagnostic/feature.
- `side_balance_downside_interaction_score` as a diagnostic/feature.
- `risk_only`, `risk_and_abs_drift`, `risk_and_overrepresented`, `risk_and_underrepresented`, `interaction_score` screen-effect tables as pointwise diagnostics.
- Unit coverage that prior features use only prior months and matching context.

Not accepted:

- Hard gate on `prior_downside_risk_score`.
- Hard gate on side-balance x downside interaction.
- Direct score multiplier based on interaction.
- Promotion of q99 pointwise improvements without stateful replacement backtest, more chronological windows, and q95/q99-specific validation.

Standard policy remains NoTrade.

## Next

1. Convert `prior_downside_risk_score` and `side_balance_downside_interaction_score` into low-capacity selector/ranking features, not hard blockers.
2. Split the next model target into at least two heads: prior downside / direction-side inversion and exit capture / executable EV.
3. Keep q95 and q99 policy families separated; do not transfer q99 screen thresholds to q95.
4. Add stateful replacement-aware backtest before treating pointwise screen gains as policy gains.
5. Add more chronological validation windows before any side-balance/downside correction can become standard.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_balance_downside_interaction.py tests/test_entry_ev_side_balance_downside_interaction.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_balance_downside_interaction`: OK
- Side-balance x downside interaction diagnostics: OK
