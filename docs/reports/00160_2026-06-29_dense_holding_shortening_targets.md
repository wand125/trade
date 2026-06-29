# Dense Holding Shortening Targets

日時: 2026-06-29 18:45 JST
更新日時: 2026-06-29 18:45 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00159` の直接cap診断は有効だったが、common tradeに限定された疎なpost-hoc targetだった。そこで、全decision rowから学べる dense な holding短縮targetをdataset schemaへ追加した。

追加した中心targetは、barrier/time exit時点の実現PnLと、固定horizon決済がそのexit-event決済より良いかを表すdelta / beat label。これにより、モデルは「入る方向」だけでなく「標準exitを待つより60/240/720分で手放すべきか」を連続値と分類の両方で学習できる。

これは実装とdataset smokeの完了であり、policy成績の改善確認ではない。次は主dataset再生成、chronological OOF、holding policyへの接続で検証する。

## Implementation

変更:

- `src/trade_data/dataset.py`
  - `long_exit_event_raw_pnl`, `short_exit_event_raw_pnl`
  - `long_exit_event_adjusted_pnl`, `short_exit_event_adjusted_pnl`
  - `long/short_fixed_60m/240m/720m_minus_exit_event_adjusted_pnl`
  - `long/short_fixed_60m/240m/720m_beats_exit_event`
- `src/trade_data/modeling.py`
  - `policy` / `full` target-setに exit-event adjusted PnL と fixed-vs-event deltaを回帰targetとして追加。
  - fixed-vs-event beat labelを分類targetとして追加。
  - `prediction_frame` に新しい実測target列を残す。

`fixed_{minutes}m_minus_exit_event_adjusted_pnl` は、値が正なら固定horizon決済のほうがbarrier/time exitより良い。`*_beats_exit_event` はその二値化。

## Smoke Dataset

2025-08をsmoke用ignored directoryへ再生成した。

Command:

```bash
python3 -m trade_data.dataset build \
  --month 2025-08 \
  --data data/processed/histdata/xauusd/xauusd_m1.parquet \
  --output-dir data/processed/datasets/xauusd_m1_dense_holding_target_smoke \
  --horizon-hours 24 \
  --warmup-days 14 \
  --post-days 4 \
  --min-adjusted-edge 15 \
  --profit-multiplier 1.0 \
  --loss-multiplier 1.2 \
  --include-fft
```

Result:

- rows: `28,971`
- output: `data/processed/datasets/xauusd_m1_dense_holding_target_smoke/xauusd_m1_2025-08_h24_edge15.parquet`
- label counts: short `9,434`, flat `5,036`, long `14,501`

New target distribution:

| target | notna | mean | p10 | p50 | p90 |
|---|---:|---:|---:|---:|---:|
| `long_exit_event_adjusted_pnl` | `28,971` | `0.1199` | `-16.0080` | `-0.1920` | `16.0000` |
| `short_exit_event_adjusted_pnl` | `28,971` | `-2.7898` | `-16.1760` | `-15.0240` | `15.8100` |
| `long_fixed_60m_minus_exit_event_adjusted_pnl` | `28,971` | `-0.0980` | `-18.0934` | `0.2510` | `17.4060` |
| `short_fixed_60m_minus_exit_event_adjusted_pnl` | `28,971` | `2.0451` | `-16.5380` | `4.1316` | `18.3400` |
| `long_fixed_240m_minus_exit_event_adjusted_pnl` | `28,971` | `0.9032` | `-16.9280` | `0.0000` | `17.9366` |
| `short_fixed_240m_minus_exit_event_adjusted_pnl` | `28,971` | `0.4160` | `-16.7110` | `0.0000` | `17.8160` |
| `long_fixed_720m_minus_exit_event_adjusted_pnl` | `28,971` | `3.6415` | `-13.0000` | `1.6596` | `21.2772` |
| `short_fixed_720m_minus_exit_event_adjusted_pnl` | `28,971` | `-3.4461` | `-20.9780` | `-0.7644` | `14.1720` |

Beat rates:

| target | rate |
|---|---:|
| `long_fixed_60m_beats_exit_event` | `0.5032` |
| `short_fixed_60m_beats_exit_event` | `0.5530` |
| `long_fixed_240m_beats_exit_event` | `0.4983` |
| `short_fixed_240m_beats_exit_event` | `0.4988` |
| `long_fixed_720m_beats_exit_event` | `0.5391` |
| `short_fixed_720m_beats_exit_event` | `0.4114` |

## Interpretation

60分beat labelは極端に片寄っておらず、分類targetとして使える密度がある。delta targetも全行で非欠損になり、exit timing / EV calibrationの補助回帰targetとして使える。

注意点:

- 旧datasetには新列がないため、新targetを学習する実験では主datasetを再生成する。
- `filter_available_target_names` により旧datasetを読む過去実験は新targetを自動で落とせるが、新targetの効果検証には再生成が必須。
- このtargetは「常に60分で切る」ruleではなく、side/regime/contextを見て短縮が有利な度合いを学習するための情報にする。

## Verification

- `python3 -m unittest tests.test_dataset tests.test_modeling`: OK, 52 tests
- `python3 -m py_compile src/trade_data/dataset.py src/trade_data/modeling.py`: OK
- smoke dataset build: OK
- smoke summary target_columns: new columns present

## Next Actions

1. `xauusd_m1_p1_l1p2_policy_combined` 系の主datasetを新schemaで再生成する。
2. policy HGB / shared MLPを再学習し、新targetのOOF regression / classification指標を確認する。
3. `pred_fixed_60m_minus_exit_event_adjusted_pnl` と `pred_fixed_60m_beats_exit_event_prob_1` をholding短縮・exit選択の補助scoreへ接続する。
4. 既存のpost-hoc `range_low_vol:london/rollover` 除外と比較し、固定ruleではなく予測targetで同等以上のcontext-aware判断ができるかを見る。
