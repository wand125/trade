# Next-bar EV goal

次足方向モデルが返す校正済み確率を、方向モデルから独立した値幅・tail risk・コストモデルと組み合わせ、売買可能な期待値へ変換する。

完成条件は、未来情報を使わないchronological OOSで次をすべて満たすこと。

- 方向accuracyではなく、実現損益とコスト控除後損益が正。
- 固定した採用条件が複数foldで再現する。
- round-trip costを引いた後も正。
- 予測EVの過大評価が許容範囲内。
- tail riskと最大drawdownが基準内。
- 既存戦略へ接続する場合は、no-replacement診断後にstateful replayでも改善する。

条件を満たさない場合の標準判断は `NoTrade` とする。方向確率が校正されていても、値幅とコストを含む収益性は保証しない。
