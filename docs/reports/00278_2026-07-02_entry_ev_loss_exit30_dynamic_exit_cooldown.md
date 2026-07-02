# Entry EV Loss Exit30 Dynamic Exit Cooldown

日時: 2026-07-02 09:28 JST
更新日時: 2026-07-02 09:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00277で残った課題「`loss_exit30` による過剰回転と悪い追加entry」を狙い、dynamic exit後の minimum hold / cooldown overlayを追加した。
- `ModelPolicyConfig` に `dynamic_exit_min_holding_minutes` と `dynamic_exit_cooldown_minutes` を追加し、post-processではなくstateful signal生成段階で再entryを制限できるようにした。
- 内部chronologyでは、minimum hold単独はtailを悪化させた。一方、cooldownは有効で、`loss_exit30_cd15` は total `+83.5766`, month min `-6.8324`, 164 trades、`loss_exit30_cd60` は total `+82.9864`, month min `-5.9400`, 123 trades。
- 外部HGBへ固定適用すると、`loss_exit30_cd15` は total `+28.4894`, month min `+0.0074` でselector pass。`cd60` は total `+35.4400` だが HGB 2025-08 roleが `-0.4100` でrole floorを落とした。
- 外部hybridでは、`loss_exit30_cd15` / `cd60` とも2025-12 `-4.1460` を消せず、totalも `loss_exit30` より落ちた。
- 内部+外部統合では `loss_exit30_cd15` が total `+118.6900`, positive roles `6/6`, role min `+0.0074`, month min `-6.8324`, 266 trades。00277の `loss_exit30` total `+112.0990`, month min `-11.3450`, 494 tradesより改善した。
- 判断: cooldown hookはaccepted infrastructure。q95 + `loss_exit30_cd15` は次の固定診断候補へ昇格。ただしmonth floorはまだ負、fresh/hybrid supportも薄いため、標準policyはNoTradeのまま。

## Artifacts

- Updated core:
  - `src/trade_data/backtest.py`
- Updated exit timing replay:
  - `scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py`
- Updated tests:
  - `tests/test_backtest.py`
  - `tests/test_entry_ev_quantile_exit_timing_sensitivity.py`
- Internal cooldown sweep:
  - `data/reports/backtests/20260702_001515_20260702_entry_ev_loss_exit30_dynamic_exit_guard_s1/`
- Internal deltas:
  - `data/reports/backtests/20260702_002651_20260702_entry_ev_loss_exit30_cd15_delta_s1/`
  - `data/reports/backtests/20260702_002700_20260702_entry_ev_loss_exit30_cd60_delta_s1/`
- External fixed checks:
  - `data/reports/backtests/20260702_002740_20260702_entry_ev_external_hgb_loss_exit30_cooldown_fixed_s1/`
  - `data/reports/backtests/20260702_002804_20260702_entry_ev_external_hybrid_loss_exit30_cooldown_fixed_s1/`

## Method

Fixed baseline:

```text
candidate: q95_sg95_rank90_floor5_side_regime_session_month
base dynamic exit: loss_first_exit_threshold = 0.30
profit_multiplier: 1.0
loss_multiplier: 1.2
max_predicted_hold_minutes: 720
```

New overlay parameters:

```text
dynamic_exit_min_holding_minutes:
  dynamic exit can fire only after this many minutes have elapsed since entry.

dynamic_exit_cooldown_minutes:
  after a dynamic exit fires, new entries are blocked until cooldown expires.
```

Internal variants:

| group | variants |
|---|---|
| baseline | `base`, `loss_exit30` |
| minimum hold | `mh5`, `mh15`, `mh30`, `mh60` |
| cooldown | `cd5`, `cd15`, `cd30`, `cd60` |
| combined | `mh15_cd15`, `mh30_cd15`, `mh30_cd30` |

External fixed variants:

```text
loss_exit30
loss_exit30_cd15
loss_exit30_cd60
```

## Internal Results

| variant | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| `loss_exit30_cd15` | `+83.5766` | `-6.8324` | `164` | `30.8714` | `0.6037` |
| `loss_exit30_cd60` | `+82.9864` | `-5.9400` | `123` | `29.5634` | `0.5610` |
| `loss_exit30_cd30` | `+73.4014` | `-6.8324` | `142` | `29.5634` | `0.5845` |
| `loss_exit30_cd5` | `+66.2862` | `-7.5660` | `224` | `32.2310` | `0.6250` |
| `loss_exit30` | `+67.5682` | `-11.3450` | `353` | `33.9764` | `0.6431` |
| `loss_exit30_mh5` | `+51.6900` | `-39.6150` | `226` | `39.6150` | `0.6283` |
| `loss_exit30_mh15` | `+8.7388` | `-61.7640` | `166` | `61.7640` | `0.6084` |
| `loss_exit30_mh60` | `+10.2260` | `-73.0890` | `131` | `73.0890` | `0.5802` |
| `loss_exit30_mh30_cd15` | `+99.3392` | `-73.5626` | `131` | `73.5626` | `0.5954` |
| `base` | `-14.6536` | `-140.8024` | `119` | `140.8024` | `0.5714` |

Reading:

- cooldown単独は、trade数を減らしながらtotalとworst monthを改善した。
- minimum hold単独は、loss-first exitの利点を遅らせてtailを戻すため本流にしない。
- `mh30_cd15` はtotalだけなら最大だが、2025-05 `-73.5626` を作るためreject。
- 内部だけなら `cd15` はtotal重視、`cd60` はtail/churn重視。

## Internal Delta

`loss_exit30` -> `loss_exit30_cd15`:

| metric | value |
|---|---:|
| base trades | `353` |
| candidate trades | `164` |
| base pnl | `+67.5682` |
| candidate pnl | `+83.5766` |
| delta | `+16.0084` |
| removed positive | `+91.1700` |
| removed negative | `-102.3084` |
| added positive | `+6.8500` |
| added negative | `-1.9800` |

`loss_exit30` -> `loss_exit30_cd60`:

| metric | value |
|---|---:|
| base trades | `353` |
| candidate trades | `123` |
| base pnl | `+67.5682` |
| candidate pnl | `+82.9864` |
| delta | `+15.4182` |
| removed positive | `+106.8030` |
| removed negative | `-122.2212` |
| added positive | `0.0000` |
| added negative | `0.0000` |

Reading:

- cooldownは悪い追加entryを抑えるという仮説に合う。
- `cd15` は少しだけreplacementを許すが、added negativeは `-1.9800` まで縮む。
- `cd60` はほぼ純粋なtrade削除で、追加entry由来の損益を作らない。
- ただし `cd15` は2025-02/04/09、`cd60` は2025-02/03/04/07/08でbaselineより悪化するため、単純に強いわけではない。

## External Fixed Check

HGB external:

| variant | total pnl | worst month | trades | selector |
|---|---:|---:|---:|---|
| `loss_exit30_cd15` | `+28.4894` | `+0.0074` | `96` | pass |
| `loss_exit30_cd60` | `+35.4400` | `-0.4100` | `86` | NoTrade |
| `loss_exit30` | `+35.2568` | `-0.0622` | `133` | NoTrade |
| `base` | `-48.2026` | `-55.4548` | `75` | NoTrade |

Hybrid external:

| variant | total pnl | worst month | trades | selector |
|---|---:|---:|---:|---|
| `loss_exit30` | `+9.2740` | `-4.1460` | `8` | NoTrade |
| `loss_exit30_cd15` | `+6.6240` | `-4.1460` | `6` | NoTrade |
| `loss_exit30_cd60` | `+1.9140` | `-4.1460` | `5` | NoTrade |
| `base` | `-12.1040` | `-26.7600` | `4` | NoTrade |

Reading:

- `cd15` はHGBの小さな負け月を消し、外部HGBでは初めてselector passした。
- `cd60` はHGB totalを維持するが、HGB 2025-08を `-0.4100` にしてrole floorを落とす。
- hybridの負けはcooldownでは消えない。これはentry churnではなく、残る数trade自体の方向/exit-capture問題。

## Combined View

Internal + external HGB + external hybrid:

| variant | total pnl | role min | positive roles | month min | trades | max DD |
|---|---:|---:|---:|---:|---:|---:|
| `loss_exit30_cd15` | `+118.6900` | `+0.0074` | `6/6` | `-6.8324` | `266` | `30.8714` |
| `loss_exit30_cd60` | `+120.3404` | `-0.4100` | `5/6` | `-5.9400` | `214` | `29.5634` |
| `loss_exit30` | `+112.0990` | `+2.6780` | `6/6` | `-11.3450` | `494` | `33.9764` |

Role totals for `loss_exit30_cd15`:

| role | total | min month | trades |
|---|---:|---:|---:|
| cal2024_validation | `+8.8424` | `0.0000` | `31` |
| fresh2024_validation | `+8.3344` | `-0.6120` | `3` |
| hgb2024_0306_external | `+28.4820` | `+0.9578` | `84` |
| hgb2025_08_external | `+0.0074` | `+0.0074` | `12` |
| hybrid2025_0912_external | `+6.6240` | `-4.1460` | `6` |
| refit2025_validation | `+66.3998` | `-6.8324` | `130` |

Remaining negative months for `loss_exit30_cd15`:

| role | month | pnl | trades |
|---|---|---:|---:|
| refit2025_validation | 2025-09 | `-6.8324` | `8` |
| refit2025_validation | 2025-06 | `-6.5136` | `6` |
| refit2025_validation | 2025-02 | `-6.0104` | `11` |
| hybrid2025_0912_external | 2025-12 | `-4.1460` | `2` |
| refit2025_validation | 2025-08 | `-3.0500` | `3` |
| refit2025_validation | 2025-03 | `-2.4566` | `11` |
| hybrid2025_0912_external | 2025-11 | `-0.7200` | `1` |
| fresh2024_validation | 2024-11 | `-0.6120` | `1` |
| fresh2024_validation | 2024-03 | `-0.3636` | `1` |
| refit2025_validation | 2025-04 | `-0.3000` | `28` |
| refit2025_validation | 2025-10 | `-0.0046` | `8` |

## Decision

Accepted:

- `dynamic_exit_min_holding_minutes` / `dynamic_exit_cooldown_minutes` as backtest infrastructure
- 7-field exit timing variants in `entry_ev_quantile_exit_timing_sensitivity.py`
- q95 + `loss_exit30_cd15` as the next fixed diagnostic candidate

Rejected:

- minimum hold as the main overlay
- `loss_exit30_cd60` as current fixed candidate, because it makes HGB 2025-08 role negative despite better combined total/worst month
- `mh30_cd15` despite high total, because it reintroduces a large May tail
- standardizing `loss_exit30_cd15` before fixing remaining month floor / support issues

Standard policy remains NoTrade.

## Next

1. Keep q95 + `loss_exit30_cd15` fixed as the next diagnostic candidate.
2. Split the remaining `cd15` negative months into:
   - refit churn/side-specific losses: 2025-02/03/06/08/09
   - hybrid sparse residual losses: 2025-11/12
   - fresh sparse one-trade losses: 2024-03/11
3. Add loss-first probability quantile/calibration so `0.30` is not a raw absolute threshold.
4. For hybrid residual losses, return to direction/exit-capture features rather than increasing cooldown.
5. Do not standardize until month floor is non-negative or a documented relaxed admission rule is explicitly accepted.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/entry_ev_quantile_exit_timing_sensitivity.py tests/test_backtest.py tests/test_entry_ev_quantile_exit_timing_sensitivity.py`: OK
- `python3 -m unittest tests.test_entry_ev_quantile_exit_timing_sensitivity tests.test_backtest`: OK
- Internal cooldown sweep: OK
- Internal `cd15` / `cd60` variant deltas: OK
- External HGB fixed check: OK
- External hybrid fixed check: OK
