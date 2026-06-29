# Holding Shortening Quality Features

日時: 2026-06-29 20:15 JST
更新日時: 2026-06-29 20:15 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`00165` で、holding-shortening probability / quantile を直接policyのcap発火に使う方向は本流から外した。今回は、その反省を受けて、holding-shortening を trade quality / trade overestimate 系の補助特徴として使えるように配線した。

今回の変更はPnL改善実験ではなく、次のOOF/chronological評価へ進むための特徴量接続である。既存predictionに列が無い場合は 0 埋めになるため、既存artifactの挙動は変えない。

## Changes

`TRADE_QUALITY_OPTIONAL_SIDE_FEATURE_SPECS` に以下を追加した。

- `pred_taken_holding_shortening_60m_prob`
- `pred_taken_holding_shortening_240m_prob`
- `pred_taken_holding_shortening_720m_prob`
- `pred_taken_holding_shortening_60m_valid_quantile`
- `pred_taken_holding_shortening_60m_multimonth_quantile`
- 上記それぞれの `pred_opposite_*` と `*_gap`

元列は以下を読む。

- `pred_long/short_fixed_60m_beats_exit_event_prob_1`
- `pred_long/short_fixed_240m_beats_exit_event_prob_1`
- `pred_long/short_fixed_720m_beats_exit_event_prob_1`
- `pred_long/short_fixed_60m_beats_exit_event_valid_quantile`
- `pred_long/short_fixed_60m_beats_exit_event_multimonth_quantile`

また、`prepare_analysis_predictions` / `enrich_trades_with_predictions` に `extra_prediction_columns` を追加し、trade-quality用の任意特徴の元列をselected tradesへ結合できるようにした。デフォルトは空なので、通常のbacktest分析経路は従来通り。

## Verification

- `python3 -m unittest tests.test_meta_model`: OK, 48 tests
- `python3 -m unittest tests.test_backtest`: OK, 82 tests
- `python3 -m unittest tests.test_docs_reports`: OK, 3 tests

`tests.test_docs_reports` は、レポート順序が `更新日時` やmtimeではなく本文内の `日時` で決まることも確認している。

## Decision

holding-shortening は、直接cap発火ではなく、entry/exit risk modelの補助特徴として扱う。次は、holding-shortening列を含むmerged predictionを使って、trade overestimate / quality のOOFとchronological applyを比較する。
