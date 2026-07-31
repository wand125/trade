# Entry EV Loss Exit30 Fixed Internal Chronology

日時: 2026-07-02 09:05 JST
更新日時: 2026-07-02 09:05 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00276でpre-register候補にした q95/floor5/rank90 + `loss_exit30` を、threshold再探索なしで内部chronology `cal2024/fresh2024/refit2025` へ固定適用した。
- `scripts/experiments/entry_ev_variant_trade_delta_diagnostics.py` を追加し、同一run内の `base` vs `loss_exit30` variantをtrade deltaで比較できるようにした。
- 内部chronologyでは q95 base `-14.6536`, worst month `-140.8024`, 119 trades に対し、`loss_exit30` は `+67.5682`, worst month `-11.3450`, 353 trades。
- 00276の外部HGB/hybridと統合すると、q95 + `loss_exit30` は total `+112.0990`, positive roles `6/6`, role min `+2.6780`, 494 trades。
- ただし month min `-11.3450` が残り、refit2025で負け月が多い。内部run admissionも `month_pnl_below_floor;role_trades_low;month_trades_low;side_share_high` でNoTrade。
- trade deltaでは、改善は既存tradeを消すことではなく、共通tradeの早期決済改善 `+33.0386` と追加entry net `+47.3832` の合算。追加entryは `+170.4600 / -123.0768` と損失も大きく、過剰回転リスクが残る。
- 判断: `loss_exit30` は追加chronologyで強く再現し、diagnostic candidateからpre-standard candidateへ一段上げる。ただし標準policyはまだNoTrade。次は trade delta の悪い追加entryを抑えるか、loss-first thresholdをabsoluteではなくcalibrated/quantile化する。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_variant_trade_delta_diagnostics.py`
- Added test:
  - `tests/test_entry_ev_variant_trade_delta_diagnostics.py`
- Fixed internal replay:
  - `data/reports/backtests/20260701_235937_20260702_entry_ev_internal_chronology_loss_exit30_fixed_s1/`
- Variant trade delta:
  - `data/reports/backtests/20260702_000414_20260702_entry_ev_internal_chronology_loss_exit30_delta_s1/`

## Method

Fixed candidate:

```text
candidate: q95_sg95_rank90_floor5_side_regime_session_month
variant: loss_exit30
loss_first_exit_threshold: 0.30
score_kind: exit_regret_selector_replguard_preblockgap_confidenceexit_bucket_t0p4
max_predicted_hold_minutes: 720
profit_multiplier: 1.0
loss_multiplier: 1.2
```

Applied chronologies:

| family | months |
|---|---|
| cal2024 | 2024-01..02 |
| fresh2024 | 2024-03..12 |
| refit2025 | 2025-01..12 |

Important: threshold and candidate were fixed from 00276. This run did not sweep `loss_exit20/25/35`.

## Internal Replay

| variant | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| base | `-14.6536` | `-140.8024` | `119` | `140.8024` | `0.5714` |
| loss_exit30 | `+67.5682` | `-11.3450` | `353` | `33.9764` | `0.6431` |

Role totals:

| role | base total | loss_exit30 total | loss_exit30 worst month | loss_exit30 trades |
|---|---:|---:|---:|---:|
| cal2024_validation | `-1.6986` | `+4.8064` | `0.0000` | `65` |
| fresh2024_validation | `+32.7380` | `+8.3344` | `-0.6120` | `3` |
| refit2025_validation | `-45.6930` | `+54.4274` | `-11.3450` | `285` |

Key monthly changes:

| month | base pnl | loss_exit30 pnl | delta |
|---|---:|---:|---:|
| 2025-05 | `-140.8024` | `-11.3450` | `+129.4574` |
| 2025-06 | `-55.4316` | `-6.6630` | `+48.7686` |
| 2025-12 | `-10.2082` | `+10.7920` | `+21.0002` |
| 2024-03 | `+24.0400` | `-0.3636` | `-24.4036` |
| 2025-02 | `+35.0866` | `-0.8614` | `-35.9480` |
| 2025-04 | `+50.6728` | `+7.3978` | `-43.2750` |

Reading:

- May/June tailは大きく縮む。
- 2025-02/04の大きな勝ちをかなり削るため、単純な早切りは利益捕捉も犠牲にしている。
- fresh2024は3 tradesのままでsupport不足。role totalはプラスだが、標準gate上の支えには弱い。

## Combined View

00276 external HGB/hybrid + 00277 internal chronologiesを統合した q95 + `loss_exit30`:

| metric | value |
|---|---:|
| total pnl | `+112.0990` |
| role min | `+2.6780` |
| positive roles | `6/6` |
| month min | `-11.3450` |
| trades | `494` |
| max DD | `33.9764` |

Role totals:

| role | total | min month | trades |
|---|---:|---:|---:|
| cal2024_validation | `+4.8064` | `0.0000` | `65` |
| fresh2024_validation | `+8.3344` | `-0.6120` | `3` |
| hgb2024_0306_external | `+32.5788` | `-0.0622` | `103` |
| hgb2025_08_external | `+2.6780` | `+2.6780` | `30` |
| hybrid2025_0912_external | `+9.2740` | `-4.1460` | `8` |
| refit2025_validation | `+54.4274` | `-11.3450` | `285` |

Negative months remaining:

| role | month | pnl | trades |
|---|---|---:|---:|
| hgb2024_0306_external | 2024-05 | `-0.0622` | `23` |
| hybrid2025_0912_external | 2025-11 | `-0.7200` | `1` |
| hybrid2025_0912_external | 2025-12 | `-4.1460` | `2` |
| fresh2024_validation | 2024-03 | `-0.3636` | `1` |
| fresh2024_validation | 2024-11 | `-0.6120` | `1` |
| refit2025_validation | 2025-02 | `-0.8614` | `22` |
| refit2025_validation | 2025-03 | `-1.9268` | `22` |
| refit2025_validation | 2025-05 | `-11.3450` | `37` |
| refit2025_validation | 2025-06 | `-6.6630` | `10` |
| refit2025_validation | 2025-08 | `-2.4780` | `7` |
| refit2025_validation | 2025-09 | `-5.7044` | `10` |
| refit2025_validation | 2025-10 | `-1.6306` | `15` |

Reading:

- all-role positiveまで進んだのは大きい。
- 残課題は「月別に小さく負ける」ことと、refit2025での追加entryの質。
- `NoTrade` から標準policyへ移すには、month floorか、month-lossを検知するexit-risk calibrationが必要。

## Trade Delta

Base vs `loss_exit30` on internal chronology:

| delta status | rows | base pnl | candidate pnl | pnl delta |
|---|---:|---:|---:|---:|
| common | `118` | `-12.8536` | `+20.1850` | `+33.0386` |
| only_base | `1` | `-1.8000` | `0.0000` | `+1.8000` |
| only_candidate | `235` | `0.0000` | `+47.3832` | `+47.3832` |

Only-candidate breakdown:

| family | rows | candidate pnl | added positive | added negative |
|---|---:|---:|---:|---:|
| cal2024 | `45` | `-1.7158` | `+7.3730` | `-9.0888` |
| refit2025 | `190` | `+49.0990` | `+163.0870` | `-113.9880` |

Reading:

- 早期決済はcommon tradeのtail圧縮として効く。
- さらに早く手放すことで新しいentry機会が増え、netでプラスになる。
- しかし追加entryの負けも大きい。特にrefit2025 only-candidate negative `-113.9880` は、次のrisk filter対象。
- `loss_exit30` はexit timingだけでなく、entry opportunity generatorとしても振る舞っている。評価ではこの2つを分ける必要がある。

## Decision

Accepted:

- q95 + `loss_exit30` fixed internal chronology replay
- variant trade delta diagnostics
- `loss_exit30` as a pre-standard diagnostic candidate

Rejected:

- standardizing `loss_exit30` immediately
- treating all-role positive as sufficient while month floor is negative
- ignoring additional-entry losses introduced by early exits

Standard policy remains NoTrade.

## Next

1. Use variant delta rows to target bad only-candidate entries, especially refit2025 additional-entry losses.
2. Add loss-first threshold quantile/calibration so `0.30` is not an absolute probability magic number.
3. Check whether a minimum hold or cooldown after dynamic exit reduces churn without losing May/June tail improvement.
4. Keep q95 + `loss_exit30` frozen while testing overlays; do not retune q/floor/rank on the same chronologies.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_variant_trade_delta_diagnostics.py tests/test_entry_ev_variant_trade_delta_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_variant_trade_delta_diagnostics`: OK
- q95 + `loss_exit30` fixed internal replay: OK
- variant trade delta diagnostics: OK
