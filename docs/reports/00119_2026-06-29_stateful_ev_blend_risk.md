# Stateful EV Blend Risk

日時: 2026-06-29 09:05 JST
更新日時: 2026-06-29 09:05 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00118` で作った `stateful_entry_value` meanを、entry EVの直接置換ではなく raw EV の過大評価penaltyとして使う。

検証式:

```text
adjusted_ev = raw_ev - alpha * max(raw_ev - stateful_mean, 0)
```

既存backtestの `risk_penalty` と `pred_candidate_quality_stateful_entry_<side>_overestimate_risk` は、overestimate riskが負値なので上式と同じ意味になる。

## 条件

共通条件:

- policy: `timed_ev`
- entry threshold: `12`
- short entry threshold offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- max predicted hold minutes: `480`
- holding column: `pred_mlp_<side>_exit_event_minutes`
- side EV penalty: `short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:10`
- profit/loss: `1.0 / 1.20`

評価対象:

- validation: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- apply holdout: `2024-12`, `2025-02`, `2025-03`
- prediction artifact: `data/reports/modeling/20260628_235629_stateful_entry_value_model/`

## Validation

artifacts: `data/reports/backtests/stateful_entry_blend_risk_validation/`

| risk penalty | sum adjusted pnl | min month pnl | trades | max DD | forced exit max |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `622.6486` | `138.0338` | `275` | `85.0166` | `0.0000` |
| `0.10` | `571.1410` | `70.0596` | `244` | `87.2394` | `0.0000` |
| `0.25` | `416.3896` | `73.3056` | `149` | `92.1786` | `0.0000` |
| `0.50` | `11.8280` | `-22.0960` | `6` | `42.1320` | `0.0000` |
| `0.75` | `0.0000` | `0.0000` | `0` | `0.0000` | `0.0000` |

`0.10` は2024-11だけ改善するが、2024-09を `138.0338 -> 70.0596` へ大きく削る。`0.25` 以上は取引数を落としすぎ、`0.50/0.75` はほぼNoTrade寄りになる。

## Apply Holdout

validationでは採用根拠が弱いが、早すぎる棄却を避けるため `0.10/0.25` もapply holdoutで確認した。

artifacts: `data/reports/backtests/stateful_entry_blend_risk_apply/`

| risk penalty | sum adjusted pnl | min month pnl | trades | max DD | forced exit max |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `242.5008` | `-20.8252` | `426` | `122.9852` | `0.0326` |
| `0.10` | `96.6198` | `-25.6206` | `367` | `104.3432` | `0.0357` |
| `0.25` | `-97.7512` | `-55.5170` | `218` | `99.7698` | `0.0000` |

月別では `0.10` が2024-12を `-20.8252 -> -10.1916` に改善する一方、2025-02を `179.2484 -> 132.4320`、2025-03を `84.0776 -> -25.6206` へ壊す。`0.25` は全体として過剰抑制。

## 判断

`stateful_entry_value` の overestimate risk を単純な線形penaltyとして標準policyに入れる方針は採用しない。

理由:

- validationで `risk_penalty=0` がsum/minとも最良。
- applyでも `0.10` は2024-12だけを救い、2025-03を大きく壊す。
- stateful meanはraw EVの平均過大評価を縮めるが、順位付け能力が弱いため、penalty化すると良い取引まで削る。
- `alpha` を強くするとNoTradeに近づき、月10 tradesの研究条件からも離れる。

次は scalar penalty ではなく、以下の方向に寄せる。

1. `stateful_positive_cost_value` targetを作り、勝ち機会の取り逃しをより強く教師化する。
2. raw EVを削るのではなく、近接候補のtie-breakにだけstateful列を使う。
3. examplesを追加月へ広げ、254例の小標本問題を緩和してから再学習する。
4. stateful targetのmonth/regime別driftを診断し、単一alphaではなく「どの局面で過大評価するか」を扱う。
