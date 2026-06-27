# Research Direction Review

日時: 2026-06-28 06:06 JST

## 目的

長時間学習を実行している間に既存docsを再読し、研究の方向性がずれていないか、袋小路に入っていないかを整理する。

## 読み直した主なdocs

- `GOAL.md`
- `docs/research_plan.md`
- `docs/modeling_strategy.md`
- `docs/experiment_protocol.md`
- `docs/status.md`
- `docs/data_strategy.md`
- `docs/backtest_spec.md`
- `docs/ideas.md`
- `docs/decisions/0003_overfitting_and_walk_forward.md`
- `docs/decisions/0004_relaxed_adjusted_pnl.md`
- `docs/decisions/0005_dense_entry_quality_targets.md`
- `docs/reports/2026-06-28_multifold_policy_selection.md`
- `docs/reports/2026-06-28_mixed_regime_weighted_training.md`
- `docs/reports/2026-06-28_dense_entry_quality_targets.md`
- `docs/reports/2026-06-28_training_time_and_generalization.md`

## 結論

研究の大枠はずれていない。バックテスト仕様、月別split、NoTrade比較、multi-fold selection、dense entry quality target、OOF meta の順に進んでおり、深層学習へ行く前の基盤作りとして妥当。

ただし、現在のHGB反復数増加とvalidation sweepの繰り返しだけで成績を追うのは袋小路になりやすい。これまでの失敗は、単純な学習不足というより、以下が重なっている。

- 同じvalidation月でpolicyを繰り返し選んでいる。
- 独立HGBではdense targetがshared representationとしてEV予測へ返らない。
- oracle best exit target と実行可能なexit判断に差がある。
- predicted EV がtestで過大評価される。
- 2024-12のようなdown/range regimeでentry方向とexit timingが同時に崩れる。
- 倍率仕様が、初期0.9/1.3、評価1.0/1.25、直近診断1.0/1.2に分かれ、標準フローと診断実験の区別を明示し続ける必要がある。

## 続けてよいこと

- 長時間学習の診断。
  - ただし採用前提ではなく、80/320/1280/低LRでR2、side accuracy、calibration後R2、executable backtestを比較する。
  - 低LRでもtestが改善しないなら、HGBの反復数探索はいったん打ち切る。
- 月10trades条件での探索。
  - 研究用には許容する。
  - ただし少数tradeの単月プラスはedgeとみなさない。
- 1.0/1.2倍率datasetの診断。
  - NoTrade寄りを緩める目的には合う。
  - ただし標準仕様へ昇格するかは、docs/decisionsで別途決める。

## 袋小路になりやすいこと

1. HGBの `max_iter` だけを伸ばす。
   - 既に320/1280でvalidation候補が出てもtestが崩れている。
   - selection量やoracle-exit pnlが増えても、executable backtestに移らなければ意味が薄い。

2. 同じvalidation 4ヶ月のsweepを何度も見てpolicyを選ぶ。
   - validation自体への過適合が進む。
   - 今後はnested/OOF selectionに寄せる。

3. `long/short/stay_flat` や単一EVだけに戻る。
   - docs上の判断どおり情報量が足りない。
   - dense targetは維持し、shared representationで使う。

4. test月の結果を見て閾値を選ぶ。
   - 2024-12/2025-02は既に多く見ているため、今後は追加holdout月を用意する。

5. データ増量を単純なtrain行数増加として扱う。
   - 目的は期間依存とregime shiftの測定。
   - walk-forward foldを増やすために使う。

## 次にやるべきこと

### 1. 失敗trade分解を先に作る

2024-12と2025-02の負けを、trade単位で以下に分解する。

- entry方向の誤り
- entryは良いがexitが遅い
- predicted EVの過大評価
- wait_regretが高いentry
- profit_barrier予測が外れたentry
- long/short別損益
- 時間帯別損益
- volatility/regime別損益
- holding minutes別損益

目的は、次のmodel変更が何を直すべきかを明確にすること。

### 2. OOFを標準化する

meta modelやpolicy selectionでは、fit月と選択月を分ける。

- train期間にもOOF predictionsを作る。
- meta学習量を増やす。
- validation月はpolicy selectionに使う。
- test月は最後に一度だけ評価する。

### 3. EV calibrationをside/regime別にする

全体のEV shrinkageだけでは足りない。

- long/short別
- volatility regime別
- trend/down/range別
- hour/session別
- predicted EV quantile別

で、予測EVと実現PnLの対応を見て、過大評価を抑える。

### 4. exit timing targetを強化する

best holding minutes回帰だけでは実行可能なclose判断へ弱い。

追加候補:

- fixed horizon return
- barrier hit time
- stop/profitどちらが先に来るか
- hazard-like close probability
- holding中にEVが劣化したか

### 5. shared representationへ進む

独立HGBでは、dense entry quality targetがEV表現を改善しない。

次の順序:

1. tabular MLPでmulti-task shared trunk
2. M1 sequence TCN
3. M1/M5 multi-branch TCN

深層学習は、OOF評価と失敗分解が揃ってから行う。

### 6. 追加holdoutを用意する

2024-12/2025-02は何度も診断に使っているため、最終判定用としては弱くなっている。

追加:

- 2023年からdown/range/upを含むholdout月
- 2025年後半の未使用月
- high volatility / low volatility別
- 連続walk-forward split

## 当面の優先順位

1. 低LR長時間学習の診断を完了し、HGB反復数探索の継続可否を決める。
2. 2024-12/2025-02のtrade failure analyzerを実装する。
3. train期間OOF predictionsを生成し、meta calibrationの学習量を増やす。
4. side/regime別EV calibrationを追加する。
5. shared representationの小型MLP/TCNへ進む。

## 判断基準

低LR長時間学習が以下を満たさない場合、HGB反復数探索はいったん終了する。

- validationだけでなくtestのside accuracyが改善する。
- executable backtestでNoTradeを上回る。
- 月10trades以上で、testの各月がプラスになる。
- max drawdownが悪化しない。

満たさない場合は、学習時間ではなく、target設計、calibration、exit timing、regime shift対応へ移る。
