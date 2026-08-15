# 00006 M15 fixed-horizon cost audit

日時: 2026-08-16 03:19 JST

## 目的

TitanFX XAUUSD-mの実spread中央値 `0.260/oz` を、M15次足より長い固定保有で吸収できるか確認した。予測モデル、confidence閾値、方向、foldは変更せず、既存M15 OOS予測を1/2/4本（15/30/60分）のopen-to-close損益へ固定展開した。

## 固定仕様

- prediction: `context_confirmation_001` と `walk_forward_001` のM15 OOS
- confidence: `>= 0.54`
- evaluation folds: `test2021`〜`test2026_partial`。EV学習seedの `test2020` は既存report 00004と同様に除外
- entry: decision timestampで始まるM15 barのopen
- exit: 1/2/4本目のM15 barのclose
- direction: decision時点で確定済みのup/downを全保有期間で固定
- cost: 1 round tripあたりspread中央値 `0.260/oz`
- loss multiplier: 1.0

途中に欠損barがある保有区間は除外する。予測時点より後の価格は実現損益だけに使い、選別や予測変更には使わない。1/2/4本は結果を見る前の固定候補であり、結果後に最良ホライズンを採用しない。

## 結果

| holding | rows | direction accuracy | gross mean / oz | median-spread後 mean / oz | gross positive folds | spread後 positive folds | all-fold cost ceiling / oz |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 bar / 15分 | 17,354 | 54.2987% | +0.09781 | -0.16219 | 6/6 | 0/6 | +0.05415 |
| 2 bars / 30分 | 17,134 | 53.8578% | +0.12298 | -0.13702 | 5/6 | 2/6 | -0.06681 |
| 4 bars / 60分 | 16,663 | 53.5438% | +0.16761 | -0.09239 | 5/6 | 2/6 | -0.12203 |

1本の17,354件、gross mean `+0.0978106`、all-fold cost ceiling `+0.0541515` はreport 00004を再現した。長期化するとaggregate gross meanは増えるが、direction accuracyは単調に低下した。2本と4本はいずれもtest2023がcost前からnegativeとなり、all-fold cost ceilingが負へ悪化した。4本でもspread中央値控除後のaggregate meanは `-0.09239/oz` である。

## 判断

固定2本・4本保有は **reject / NoTrade** とする。値幅拡大だけでは実spreadを吸収できず、期間再現性も1本より悪化した。XAUUSD-mの同じM15予測について、保有本数を履歴へ合わせて追加探索しない。1本policyの不採用、`live_action=no_trade`、authoritative予測、fair odds、paper/live policyを変更しない。

次は保有期間の調整ではなく、実spreadが十分薄い別銘柄について、予測を作る前にcost ceilingとして必要なgross edgeをscreenする。commission/slippageを取得できた場合は必ずspreadへ加算し、全fold positiveを採用条件とする。

## 成果物と検証

- 診断: `src/trade_data/next_bar_horizon.py`
- CLI: `methods/next_bar_ev/scripts/fixed_horizon.py`
- テスト: `tests/test_next_bar_horizon.py`
- 集計: `experiments/next_bar_ev/m15_fixed_horizon_cost_audit_001.json`
- 対象テスト: 8 passed（fixed horizon 5件 + existing next_bar_ev 3件）
- 実行: 既存low-priority worker、CPU only、nice/I/O低優先度。再学習なし
