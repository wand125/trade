# Trade Exposure Failure Profile

日時: 2026-06-29 07:29 JST
更新日時: 2026-06-29 07:29 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00109` で、jackknife選定候補 `down5,up10` はvalidation内部では安定していたが、既存holdout stressの2024-12で崩れた。

今回は、月全体のregime構成ではなく、実際に選択されたtradeだけを予測frameと結合し、side / regime / session別の露出損益を調べる。目的は候補を後付けで選び直すことではなく、2024-12型の崩れを教師・特徴・診断へ戻すための失敗構造を特定すること。

## 実装

`model-trade-exposure` を追加した。

```bash
python3 -m trade_data.backtest model-trade-exposure \
  --runs data/reports/backtests/down5_up10_trade_exposure_base \
  --output-dir data/reports/backtests \
  --label down5_up10_trade_exposure
```

このコマンドは各 `model-policy` runの `config.json` から予測parquetを読み、`trades.csv` と `decision_timestamp` で結合する。出力は `enriched_trades.csv` と `group_by_month.csv`, `group_by_direction_combined_regime.csv`, `group_by_direction_session_regime.csv` など。

## Base Exposure

対象は `down5,up10`、loss multiplier `1.20`、base cost。

| month | split | pnl | trades | win rate | direction error | EV overestimate |
|---|---|---:|---:|---:|---:|---:|
| 2024-07 | validation | `198.1782` | `65` | `0.6769` | `0.3385` | `12.3079` |
| 2024-09 | validation | `138.0338` | `70` | `0.5429` | `0.4000` | `13.4476` |
| 2024-11 | validation | `142.8264` | `73` | `0.5753` | `0.4658` | `15.6581` |
| 2025-01 | validation | `143.6102` | `67` | `0.6119` | `0.3731` | `14.0497` |
| 2024-12 | holdout | `-20.8252` | `92` | `0.4348` | `0.5870` | `17.9451` |
| 2025-02 | holdout | `179.2484` | `182` | `0.5330` | `0.4286` | `20.4552` |
| 2025-03 | holdout | `84.0776` | `152` | `0.5395` | `0.5592` | `18.6048` |

2024-12はvalidation範囲外の低win rate / 高direction error / 高EV overestimateになった。2025-03もdirection errorとEV overestimateは高いが、取引数と勝ちtradeでPnLは残っている。

2024-12の主な損失:

| group | trades | pnl | validation support |
|---|---:|---:|---|
| `long:down_low_vol` | `21` | `-48.9630` | validation合計 `+122.6112`, 最悪月 `+15.9300` |
| `long:up_low_vol` | `31` | `-25.7044` | validation合計 `+292.9946`, 最悪月 `-1.3742` |
| `long:london` | `13` | `-100.5218` | validation合計 `+132.7926`, 最悪月 `+1.9078` |
| `short:asia` | `21` | `-13.2398` | validation合計 `+43.1986`, 最悪月 `+4.2066` |

重要なのは、2024-12で負けた露出がvalidationで明確に負けていないこと。単純なdirection/session loss gateだけでは、このタイプの未来反転を事前に落としにくい。

## Local Rule Diagnostics

2024-12の失敗露出から、2つの後付けルールを診断した。

| variant | validation sum | validation min | holdout sum | holdout min | 判断 |
|---|---:|---:|---:|---:|---|
| base | `622.6486` | `138.0338` | `242.5008` | `-20.8252` | 現行基準 |
| block `long:london`, `short:asia` | `499.9724` | `110.9922` | `261.6722` | `-39.0314` | 2024-12を悪化。採用しない |
| penalty5 `long:london`, `short:asia` | `401.9836` | `40.1824` | `243.5110` | `13.2610` | 2024-12は救うがvalidationを壊す。採用しない |

既存tradeを単純に除外する近似では改善して見えたが、実backtestではポジションが空いたことで別entryが入り、block版は2024-12を悪化させた。したがって、露出分析の結果をそのままhard blockへ変換するのは危険。

## 判断

今回の主成果は、候補改善ではなく診断軸の追加。

- `model-trade-exposure` は今後の固定候補監査に標準で使う。
- 2024-12型の崩れは、月全体のregime mixより、選択tradeのside / session / low-vol露出とEV過大評価に出る。
- ただし、validationで利益だった露出がholdoutで反転しているため、単純なsession/regime blockは過適合しやすい。
- 次はhard rule追加ではなく、entry/side confidence、EV calibration、exit timing targetへ戻し、ポジション空きによる代替entryまで含む形でrobustnessを評価する。

## Artifacts

- base model-policy runs: `data/reports/backtests/down5_up10_trade_exposure_base/`
- base exposure: `data/reports/backtests/20260628_222618_down5_up10_trade_exposure/`
- block diagnostic runs: `data/reports/backtests/down5_up10_block_long_london_short_asia_base/`
- block exposure: `data/reports/backtests/20260628_222813_down5_up10_block_long_london_short_asia_exposure/`
- penalty diagnostic runs: `data/reports/backtests/down5_up10_penalty_long_london_short_asia5_base/`
- penalty exposure: `data/reports/backtests/20260628_222923_down5_up10_penalty_long_london_short_asia5_exposure/`
- variant month summary: `data/reports/backtests/20260629_down5_up10_local_exposure_variant_summary.csv`
- variant split summary: `data/reports/backtests/20260629_down5_up10_local_exposure_variant_split_summary.csv`

## Verification

- `python3 -m unittest tests.test_backtest.BacktestTests.test_model_trade_exposure_reads_run_config_and_groups_regime_exposure`: OK
- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
- `python3 -W ignore -m unittest discover tests`: OK, 154 tests
- `git diff --check`: OK
- `python3 -m trade_data.backtest model-trade-exposure`: OK for base / block / penalty diagnostics
