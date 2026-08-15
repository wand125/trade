# Next-bar EV research

`next_bar` のout-of-sample方向予測を、売買期待値へ変換する独立層。方向モデルを損益で再学習せず、次の要素を別々に扱う。

- `confidence`: 予測方向が正しい確率。
- `predicted_gain_mean_atr`: 正解時の次足値幅。
- `predicted_loss_mean_atr`: 不正解時の次足値幅。
- `tail_loss_probability`: 指定ATR以上の逆行確率。
- `risk_adjusted_expected_ev_atr`: 任意のstress倍率を適用できるEV。標準倍率は1.0。
- `breakeven_probability`: 予測gain/loss比から求める損益分岐的中率。
- `probability_edge`: confidenceから損益分岐的中率を引いた値。
- `kelly_fraction_raw/conservative`: 確率とpayoff ratioから計算する参考値。採用検証を通るまでは発注量に使わない。
- `conservative_ev_after_cost_atr`: confidence下限、gain下位25%、loss上位75%、損失倍率、コストを含む採用用EV。

## EV walk-forward

```bash
uv run python methods/next_bar_ev/scripts/run.py \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --predictions-dir experiments/next_bar/context_confirmation_001 \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output-dir experiments/next_bar_ev/m15_run \
  --timeframes 15 \
  --min-confidence 0.54 \
  --loss-multiplier 1.00 \
  --decision-round-trip-cost 0.05
```

最初の予測foldだけを学習に使い、次foldを評価する。その後は過去foldを拡張して同じ処理を繰り返す。EVモデルから見たtest foldは常に未来である。

## 既存売買へのoverlay

```bash
uv run python methods/next_bar_ev/scripts/overlay.py \
  --trades path/to/trades.csv \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output-dir experiments/next_bar_ev/overlay_run \
  --timeframe 15 \
  --timestamp-column entry_decision_timestamp \
  --side-column direction \
  --pnl-column candidate_adjusted_pnl
```

各trade時刻以前に確定し、かつ予測対象足がまだ進行中の予測だけをas-of joinする。`long/short` と `up/down` は正規化する。出力するskip/half-sizeは既存tradeを置換しないcounterfactualであり、新しいtradeが空き時間へ入るstateful効果は含まない。

短時間のentry delayを評価する:

```bash
uv run python methods/next_bar_ev/scripts/entry_delay.py \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --trades path/to/trades.csv \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output-dir experiments/next_bar_ev/m5_entry_delay \
  --timeframe 5 \
  --confidence-threshold 0.53 \
  --max-delay-minutes 15 \
  --confirmation-start 2025-03-01
```

元entry価格と同時刻M1 openの差を遅延後openへ引き継ぎ、元のspread/約定補正を維持する。exitは元時刻に固定する。development/confirmationの両方でdelta positive、最低30 delayed rows、worst month非悪化を満たす場合だけ採用する。

固定方向予測を複数bar保有へ延長したcost耐性を診断する:

```bash
uv run python methods/next_bar_ev/scripts/fixed_horizon.py \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --predictions experiments/next_bar/context_confirmation_001/m15_walk_forward_predictions.parquet \
  --predictions experiments/next_bar/walk_forward_001/m15_walk_forward_predictions.parquet \
  --output experiments/next_bar_ev/m15_fixed_horizon_cost_audit_001.json \
  --holding-bars 1,2,4 \
  --confidence-threshold 0.54 \
  --round-trip-cost 0.26 \
  --exclude-fold test2020
```

entryはdecision bar open、exitは指定本数目のcloseで、途中に欠損barがある区間を除外する。XAUUSD-mでは2/4本とも1本よりall-fold cost ceilingが悪化したため不採用。保有本数を履歴へ合わせて追加探索しない。詳細はreport 00006。

## 採用基準

方向単独policyは次を満たす場合だけpaper candidateとする。

1. 想定all-in cost控除後に全OOS foldが正。
2. 実測live costがhistorical all-fold cost ceiling以下。
3. 固定条件を追加の完全未使用期間で確認する。
4. sizingは固定1 oz。Kelly参考値は発注量へ使わない。

EV選別policyは、上記に加えてEV biasが安定し、特定期間へ利益が集中しないことを要求する。既存戦略overlayはdevelopment/confirmationとstateful replayの両方でbaselineを上回る必要がある。

固定設定 `config/m15_paper_policy_v1.json` はhistorical research candidateとして保存する。TitanFX XAUUSD-mの2026-08-11〜08-15 EA snapshot 9,458件ではspread中央値だけで `0.260/oz` とall-fold cost ceiling `0.05415/oz` の約4.80倍だったため、この銘柄のM15次足単独policyはrejectとし、paper/live資格を与えず `live_action=no_trade` を維持する。commission/slippageは未取得だが、spreadだけでadmission failの結論は変わらない。詳細はreport 00005。

## 記録

実験判断は `docs/reports/` に番号順で保存する。生成モデルと行単位予測は `experiments/next_bar_ev/` に置き、Gitでは追跡しない。
