# Current Assessment

最終更新: 2026-06-30 14:21 JST

## 結論

現時点では、標準採用できる利益最大化トレードpolicyはない。

ただし、研究は停滞していない。データ生成、backtest、OOF、walk-forward、candidate selection、trade delta、context guard、entry budget までの検証基盤は整っている。00207で全2024を同一chronological protocolへ揃え、混合family問題は解消した。00208では calibrated entry EV + 高いshort threshold が full 2024 testでNoTradeを超えたが、validationではNoTrade tieとしてしか選べていなかった。00209でNoTrade-first selectorを実装し、00210で `min_entry_rank` を明示したrank gate / support auditへ進めた。00211では追加refit foldで、support gateが十分なvalidation-positive候補を選んでも未来10ヶ月で大きく崩れることを確認した。00212でmulti-window selectorを実装し、単一2ヶ月validationではなく複数validation windowで候補を審査できるようにした。00213でside/regime/window gateの感度を振ったが、固定テストに耐える候補は出ていない。現在の主課題は「multi-window admission selectionでNoTradeを上回る候補を作ること」と「guardで悪いtradeを消しても、空いた時間のreplacement tradeが別の損失を作ること」。

採用判断は、全期間を見たbestではなく、prior-only / chronological / fresh apply で壊れないかを優先する。

## 現在の主要評価

| 系列 | 現状 | 代表結果 | 判断 |
|---|---|---|---|
| Holding max cap | `250..260m` はholding安定化候補 | 2025-01..08 coststress `260m` は total `+458.9738`。fresh 2025-09..12 は `260m` でも `-839.2544` | 標準採用しない。fresh失敗はholdingではなくside drift |
| Full-2024 chronological protocol | 00206の混合familyを解消したcanonical 2024 artifact | 2024-05..12 OOF比較で source p10/replm10 が最良だが total `-3.1736`。risk5 side `-10.4618`、risk0 side `-32.7828`、risk0 no-side `-141.8816` | 標準採用なし。NoTrade超えまでdiagnostic |
| Entry EV calibrated admission | raw EV thresholdの過適合を診断し、calibrated EVの高threshold候補を固定testした | raw validation `entry12/short3` は `+22.7292` だが full 2024 test `-442.4662`。calibrated `entry10/short6` は test `+100.3612`, worst `-43.2296`, trades `60`; `entry12/short6` は `+74.0644`, worst `-37.8326`, trades `26` | 診断候補。validationではNoTrade tieなので標準採用しない |
| Entry EV NoTrade selector | validation-positiveでなければ標準はNoTradeにするselectorを実装 | Fresh `2024-03..04` validation bestは calibrated `entry12/short6` の `-1.8610`。standard selectorはNoTrade。diagnostic fixed testは `+65.4014`, worst `-37.8326`, trades `19` だが、00210で `min_rank0.5` 入りと訂正 | selectorはaccepted infrastructure。`cal12/short6/min_rank0.5` は診断候補のみ |
| Entry EV rank gate support | `min_entry_rank` を明示grid化し、support gateを追加 | Fresh `2024-03..04` bestは `entry10/short9/min_rank0.0` の `+17.0910`, worst `+0.7230`, trades `4`。`min_trades=10`, active2, worst0ではNoTrade。Fixed `2024-05..12` は同row `+87.8942`, worst `-2.2800`, trades `10`; `entry8/short9/min_rank0.6` は `+74.2970`, worst `-20.1600`, trades `11` | rankはdiagnostic admission axis。support不足で標準採用しない |
| Entry EV rank refit 2025 | 追加model-refit foldでsupport gateを検証 | train `2024`, validation `2025-01..02`, test `2025-03..12`。support gateは `entry12/short3/min_rank0.0` を validation `+209.4234`, worst `+71.1950`, trades `170` で選ぶが、fixed testは `-1002.1534`, worst `-294.1980`, trades `1147`。test hindsight top `entry14/short9/min_rank0.7` は `+324.5040` だがvalidation 0 trades | 標準採用なし。2ヶ月validationではregime代表性が足りない |
| Entry EV multi-window selector | 複数validation windowでNoTrade-first selectionできるようにした | fresh2024 + refit2025のstrict gateはNoTrade。relaxed gateは `entry10/short9/min_rank0.0` を validation `+190.4544`, trades `173` で選ぶが、fixed tests `2024-05..12 + 2025-03..12` では `-943.9322`。`max_side_trade_share<=0.95` ではNoTrade | accepted infrastructure。標準policyはNoTrade |
| Entry EV gate sensitivity | side/regime/window support gateをgrid評価した | `576` gate中 `568` はNoTrade、`8` は全て `entry10/short9/min_rank0.0` を選び fixed tests `-943.9322`。`max_side_trade_share<=0.95`, `min_window_trades=10`, `min_combined_regime_pnl>=-50` は全てNoTrade | accepted infrastructure。閾値調整だけでは汎化候補なし |
| Side drift guard | prior-onlyで悪いshort contextを検出できるが、short-only抑制では残存riskがlongや良いshort削除へ移る | strict short p10 + admission margin10 は 2025-01..12 total `-90.1378`。00205では `2025-04..06` raw EV short bias `+0.27..+0.30` を確認。00207の全2024 OOFではsourceが相対最良でも total `-3.1736` | 診断baseline。side/EV calibration preflightとして使い、単独policy化しない |
| Residual short failure | 残存損失はほぼshort | p10 + margin10 の負け月で short `-716.6702`、long `-8.4414` | 次はshort側のreplacement riskと初回損失制御 |
| Online context drawdown | realized lossだけで発火できる | prior-only `worst` + margin-aware は min4 total `+69.9374`、min8 total `-199.4438` | risk mandate候補。利益最大化policyではない |
| Short raw gap guard | 介入対象の発見には有効 | all-window bestは total `+18.5106` だが prior-only min4 `-274.9360` | 単独採用しない |
| Short entry budget / budget0 | active short contextを完全stay-flat化できるが、固定適用では期間依存が残る | 2025 all-window `gap5/budget0` total `+508.9838`、2024-11..2025-04 smoke `+445.8266`。一方、2024-11..2025-08の追加same-familyでは10ヶ月 `+384.6968` でも、追加apply 2025-05..08だけは `+13.9434` でsource `+66.7730` とbaseline `+176.8236` に負けた | `gap5/budget0` も標準採用しない。diagnostic baseline / intervention locatorへ降格 |
| Online context feature | post-filterでは損失説明力あり | context特徴追加はOOF AUCを改善せず。min8 large_loss AUC `0.5523 -> 0.5364` | raw feature昇格なし |
| Cooldown / recovery | hard blockの緩和 | cooldown/recoveryはprior-onlyで既存hard block系に負ける | 採用しない |

## 採用状態

採用済みインフラ:

- leak-aware dataset / label生成
- executable monthly backtest
- cost stress、loss multiplier `1.20`
- OOF / chronological / walk-forward検証
- `model-trade-delta` 系の差分診断
- side drift / residual failure / online context state 診断
- side EV penalty、admission margin、context drawdown guard、entry budget hook

診断baselineとして残すもの:

- `p10 + admission margin10`
- side-month online drawdown guard の prior-only `worst` objective
- short budget `defensive_budget` / fixed `gap0/budget0`
- short budget drift trigger `gap5/budget0 -> gap0/budget0`
- fixed short budget trigger audit `gap5/budget0 -> gap0/budget0`
- prediction side drift trigger metrics as diagnostics only
- context alert composite trigger as explanation of 00191
- alert-context budget/admission hook as diagnostics only
- alert-context first-loss / fast-stop as diagnostics only
- budget0 replacement-path decomposition as candidate adoption preflight
- replacement prior signal audit as preflight, not dynamic policy
- focused entry-level residual signal audit as preflight, not dynamic policy
- focus entry dynamic hook as diagnostics only
- replacement risk target diagnostics
- triggered replacement profit-miss hook as diagnostic candidate after same-family smoke failure
- `gap5/budget0` as diagnostic baseline / intervention locator after additional same-family apply failure
- same-family side calibration diagnostics as required preflight before adding side hooks
- early-2024 chronological risk OOF bridge artifact
- full-2024 chronological HGB+MLP artifact as canonical 2024 comparison input
- calibrated entry EV high-threshold candidates `entry10/short6` and `entry12/short6` as fresh-fold diagnostic candidates only
- entry EV NoTrade-first selector as accepted infrastructure
- calibrated `entry12/short6/min_rank0.5` as diagnostic low-frequency candidate only after 00209 correction
- entry EV rank gate and support gates as diagnostic admission infrastructure
- `entry10/short9/min_rank0.0` and `entry8/short9/min_rank0.6` as low-support diagnostic rows only
- 2025-refit entry EV rank fold as admission validation-design stress test
- test hindsight `entry14/short9/min_rank0.7` as sparse short-only diagnostic clue, not selectable policy
- multi-window entry EV admission selector
- window-level trade support and side-balance rejection gates as diagnostics
- entry EV gate sensitivity infrastructure
- holding max `250..260m` sensitivity
- `signal_short_raw_gap` as intervention locator

標準採用しないもの:

- all-windowだけで選ばれた `threshold=40/60` や `gap5/th20/m20`
- static session/regime hard block
- raw probability threshold直結の holding shortening
- global side-confidence gate
- profit-barrier hard gate / linear penalty
- selected-trade quality hard gate / direct EV replacement
- cooldown / recovery based online guard
- raw online context stateの標準feature追加
- monthly prediction-share triggerの直接採用
- context alert count / loss-bias triggerの直接採用
- alert context限定budget/admissionの標準採用
- alert context限定first-loss / fast-stopの標準採用
- focus entry OR / side-gap-only dynamic hookの標準採用
- raw EV validation winners as direct admission policies
- calibrated EV high-threshold candidates as standard policies before fresh-fold validation
- diagnostic near-NoTrade candidate as standard policy when validation total is non-positive
- low-support rank-gated candidate as standard policy when validation trades are below the support gate
- support-gate-passing `entry12/short3/min_rank0.0` from the 2025-refit fold, because future test was `-1002.1534`
- relaxed multi-window `entry10/short9/min_rank0.0`, because fixed tests were `-943.9322`
- all gate-sensitivity variants selecting `entry10/short9/min_rank0.0`, because their fixed tests are also `-943.9322`
- `max_side_trade_share=0.95` as a frozen standard threshold before testing more windows

## 中心的な失敗構造

2025-09..12 の fresh failure では、dense label distribution は long 寄りなのに、raw EV prediction と実行tradeが short 寄りになる。

代表的な症状:

- fresh 2025-09..12 の mean short overprediction は `+0.4143`
- selected short PnL は `-704.9300`、long PnL は `-134.3244`
- worst contextは `short/range_low_vol` 周辺、特に `ny_overlap`, `rollover`, `asia`
- confidenceやside gapだけでは除外できない
- guard後も replacement short が残り、損失の尾部を作る
- alert contextだけを止めても late common short `-382.7524` と replacement short `-293.7604` が残る
- `gap5` replacement shortのうち `up_low_vol/ny_overlap` は prior prediction biasで拾える。`range_low_vol/ny_overlap` は prior context signalでは拾いにくいが、entry-level side gap / rank signalを足すと大半を事前説明できる。ただしdynamic hookではreplacementが再発し、OR条件は小幅悪化した
- replacementは全期間では利益にもなるため、global hard gateは危険。late bad regimeでは `profit_hit_lt0p5` が強いが全期間では良いreplacementを消す。prior deterioration triggerと `min_prior_months=4` を加えたdynamic hookは2025 all-windowで `+790.3634` まで改善したが、2024-11..2025-04 same-family smokeでは勝ちを削った
- `gap5/budget0` 単体も、2024-11..2025-08の追加same-familyでは10ヶ月合計でsourceを上回るが、追加apply 2025-05..08だけではsourceとbaselineに負ける。特に2025-06の勝ちを削るため、同じ2025系列でshort hookを重ねるのは過適合になりやすい
- 00205では、raw EV short biasは明確だが、`gap5/budget0` 後の最大損失は `2025-07 down_low_vol/ny_overlap long -97.4172` などlong側にも移ると確認した。direction errorやEV overestimateの平均が少し良くても、PnL採用根拠にはならない
- 00206で早期2024のrisk OOFを `2024-05` まで前倒しし、00207で全2024を同一chronological protocolへ揃えた。全2024 OOFではsource p10/replm10が相対最良だが total `-3.1736` でNoTradeを超えず、side/risk hookの標準採用根拠にはならない
- 00208でraw EV thresholdのvalidation過適合が明確になった。calibrated EV + 高いshort thresholdはfull 2024 testで positive PnLを出したが、validationではNoTrade tieだったため、test-set selectionを避けるにはfresh chronological foldとNoTrade tie selectorが必要
- 00209でNoTrade-first selectorを実装した。fresh `2024-03..04` validationでは best calibrated `entry12/short6` も `-1.8610` でNoTrade未満なので、標準selectorはNoTradeを選ぶ。diagnostic fixed test `2024-05..12` は `+65.4014` だが、validation-negative候補なので標準採用しない
- 00210で00209のfixed testは `min_entry_rank=0.5` 入りだったと訂正し、rank gateを明示grid化した。fresh validationでbest `entry10/short9/min_rank0.0` は positive だが4 tradesしかない。月10trades相当のsupport gateではNoTradeを返すため、rank gateは有望な診断軸であって標準policyではない
- 00211で、追加refit foldでは逆にsupport gateを十分満たすrowが未来で壊れた。`2025-01..02` validationで `entry12/short3/min_rank0.0` は `+209.4234`, trades `170` だったが、`2025-03..12` testは `-1002.1534`。これはsupport不足ではなくvalidation windowのrepresentativeness不足で、2ヶ月validationだけでは未来regimeの防波堤にならない
- test hindsightの `entry14/short9/min_rank0.7` は `+324.5040` だがvalidation 0 tradesであり、選ぶとtest leakageになる。高rank short-only sparse entryは診断軸として残すが、selection ruleには使わない
- 00212でmulti-window selectorを実装した。fresh2024 + refit2025を同時に見ると、strict support gateはNoTrade。relaxed gateは `entry10/short9/min_rank0.0` を選ぶが、fixed testsで `-943.9322` へ崩れる。side share `0.9595` なので `max_side_trade_share<=0.95` ならNoTradeになるが、この閾値はまだ診断であり標準固定しない
- 00213でside/regime/window gate感度を576通り確認したが、policyを選ぶ8 gateは全て同じ崩壊候補だった。`max_side_trade_share<=0.95`, `min_window_trades=10`, `min_combined_regime_pnl>=-50` は全てNoTrade。fixed-test-positiveの `entry14/short9/min_rank0.6` はvalidation-negativeかつzero-support windowありなので、採用するとhindsightになる
- 両fixed test windowに存在するconfigだけのhindsight topでも `entry14/short9/min_rank0.6` total `+98.9868`, worst `-133.6912` で、robust standardには遠い

したがって、次の改善は「holding capの再探索」でも「2025系列へのshort hook追加」でもなく、entry EV calibration、rank/quantile admission control、NoTrade-first selectorを、multi-window / purged walk-forward / regime別安定性評価へ拡張することを優先する。

## 次に検証すべきこと

1. Entry admission reviewは `--multi-window` selectorとgate sensitivityを標準入口にする。単一2ヶ月validationだけで標準候補を選ばない。
2. 2025系列でshort hookをさらに積む前に、source policy自体のside prediction calibrationとregime別崩れを再評価する。
3. `pred_short_profit_barrier_hit` を0/1ではなく確率または校正済み確率に差し替えてから、profit-miss系hookを再評価する。
4. raw EV絶対値ではなく、side/regime別のrank、calibrated EV quantile、support-aware thresholdをadmission特徴として評価し、より多いvalidation windowでtotal、worst、trade support、side balance、regime worst bucketがNoTradeを超えるかを見る。
5. side prior driftを、predicted side share vs dense label side share の prior window差分で補正する。
6. 新しいcandidateは必ず NoTrade、previous diagnostic baseline、cost stress、worst month、max DD、short PnLで比較する。

## 読むべき代表レポート

- `00174`: fresh 2025-09..12 の holding cap失敗とside drift露呈
- `00175`: side drift diagnostics
- `00178`: side drift guard + admission margin
- `00179`: residual short failure diagnostics
- `00182`: context drawdown margin-aware prior selection
- `00187`: short raw gap context guard
- `00188`: short entry budget guard
- `00189`: short budget selection
- `00190`: context entry budget zero
- `00191`: short budget drift trigger
- `00192`: prediction side drift trigger
- `00193`: context alert budget trigger
- `00194`: alert context budget admission
- `00195`: alert context first loss cap
- `00196`: budget0 replacement path diagnostics
- `00197`: fixed short budget trigger audit
- `00198`: replacement prior signal audit
- `00199`: entry signal residual context audit
- `00200`: focus entry dynamic hook
- `00201`: replacement risk target diagnostics
- `00202`: triggered replacement risk hook
- `00203`: triggered profit-miss same-family check
- `00204`: gap5 budget same-family extension
- `00205`: same-family side calibration diagnostics
- `00206`: early-2024 chronological risk OOF
- `00207`: full-2024 chronological protocol
- `00208`: entry EV calibration admission
- `00209`: entry EV NoTrade selector fresh fold
- `00210`: entry EV rank gate support audit
- `00211`: entry EV rank refit 2025 fold
- `00212`: entry EV multi-window admission selector
- `00213`: entry EV gate sensitivity
