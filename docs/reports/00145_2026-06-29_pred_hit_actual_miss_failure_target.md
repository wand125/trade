# Pred Hit Actual Miss Failure Target

日時: 2026-06-29 14:58 JST
更新日時: 2026-06-29 14:58 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00144` では、2025-05 highcost risk5の残存損失が、単純な方向誤りよりも profit-barrier hit予測、EV過大評価、exit timing の過信に寄っていることを確認した。

今回はその反省を、post-hoc hard gateではなく chronological OOF で学習できる失敗targetへ戻す。特に `pred_hit_actual_miss` を「モデルはprofit barrier到達を予測したが、実際は到達しなかったtrade」として作り、policyのrisk列へ接続できるかを検証した。

## 実装

`oof-trade-failure-model` に以下を追加した。

| 追加 | 内容 |
|---|---|
| target | `pred_hit_actual_miss`, `ev_overestimate_high` |
| feature | `pred_taken_side_confidence`, `pred_opposite_side_confidence`, `pred_side_confidence_gap` |
| CLI | `--ev-overestimate-threshold` |

`pred_hit_actual_miss` は `pred_taken_profit_barrier_hit >= 0.5` かつ `actual_taken_profit_barrier_hit < 0.5`。これは予測時点で見えているprofit-barrier予測を条件にするため、rankが高く出やすい。feature/targetの因果順は守るが、AUCだけを過大評価しない。

## OOF Metrics

2024-11..2025-04の selected trades 502件で、highcost risk5 の chronological OOF trade failure modelを作った。

| target | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|
| `pred_hit_actual_miss` | `0.0717` | `0.0687` | `-0.0030` | `0.0409` | `0.9626` |
| `ev_overestimate_high` | `0.0179` | `0.0131` | `-0.0048` | `0.0178` | `0.1999` |
| `exit_regret_high` | `0.1992` | `0.1855` | `-0.0137` | `0.1671` | `0.3488` |
| `any_failure` | `0.7112` | `0.7113` | `0.0002` | `0.2101` | `0.4659` |

判断: `pred_hit_actual_miss` 以外はrank signalとして弱い。`pred_hit_actual_miss` もtarget定義上、profit-barrier予測列を含むためAUCは補助指標として扱う。

## 2025-05 Policy Screen

2025-05 highcost、profit `1.0` / loss `1.20`、spread `0.2`、slippage `0.1`、execution delay `1`、entry `12`、short offset `6`、side margin `5`、MLP holding guard `30..480m` の条件で比較した。

| run | adjusted PnL | trades | win rate | profit factor | max DD |
|---|---:|---:|---:|---:|---:|
| baseline stateful risk5 | `-52.9764` | 105 | `0.5238` | `0.9016` | `137.4392` |
| failure only risk5 | `-52.0516` | 106 | `0.5189` | `0.9000` | `143.5182` |
| failure only risk10 | `-7.1330` | 107 | `0.5327` | `0.9861` | `147.1096` |
| failure only risk20 | `-103.0830` | 106 | `0.5189` | `0.8144` | `193.3456` |
| stateful + predhit w1 risk5 | `-44.9494` | 104 | `0.5288` | `0.9123` | `147.5402` |
| stateful + predhit w2 risk5 | `-66.6922` | 105 | `0.5143` | `0.8702` | `152.2770` |
| stateful + predhit w4 risk5 | `-85.8442` | 103 | `0.5243` | `0.8429` | `199.6200` |

2025-05単月では `failure only risk10` が大きく改善した。ただしDDはbaselineより悪化し、改善が安定したrisk削減かどうかはこの月だけでは判断できない。

## OOF Validation Check

単月最適化を避けるため、2024-11..2025-04のOOF validation月へ戻して確認した。

| run | validation PnL | validation trades | min month | max DD | 2025-05 PnL |
|---|---:|---:|---:|---:|---:|
| baseline stateful risk5 | `407.8172` | 502 | `-16.9006` | `224.7524` | `-52.9764` |
| failure only risk10 | `325.8466` | 540 | `-52.4236` | `217.2848` | `-7.1330` |
| stateful + predhit w1 risk5 | `240.9596` | 515 | `-39.4490` | `234.9788` | `-44.9494` |

`failure only risk10` は2025-05を改善するが、OOF validation合計はbaseline比 `-81.9706`。`stateful + predhit w1` もvalidation合計を `-166.8576` 悪化させる。したがって、今回のrisk列を標準policyへ採用しない。

## Trade Delta

baselineから `failure only risk10` への2025-05差分は、月次PnL `+45.8434`。ただし、removed positive `106.9430`、removed negative `-65.0280`、added positive `150.6240`、added negative `-40.3512` で、単純に悪いtradeだけを消したというよりtrade集合の入れ替え効果が大きい。

悪化した主なcommon groupは `short/up_normal_vol` で、baseline `-72.1016` から candidate `-99.4040`。一方、long側では `failure only risk10` が2025-05の損失を大きく縮めた。これは当初狙ったshort profit-barrier過信の修正とは完全には一致しない。

## 判断

1. `pred_hit_actual_miss` targetの実装は残す。選択済みtrade上のprofit-barrier過信を教師化する部品として有用。
2. 今回のrisk penaltyを標準policyには採用しない。2025-05改善はあるが、OOF validationでbaselineを下回る。
3. `ev_overestimate_high` と `exit_regret_high` は現target設定ではrank能力が弱い。threshold分類より、連続値回帰、分位回帰、または保有時間targetとのjoint targetを検討する。
4. 次は `pred_hit_actual_miss` を単独riskにせず、candidate ranking / exit timing model / EV calibration featureとして使う。
5. 2025-05単月改善で閾値を追わない。採用条件は引き続き validation OOF、固定外挿月、trade delta、regime別壊れ方で見る。

## Artifacts

- OOF model: `experiments/20260629_054724_trade_failure_pred_hit_ev_overestimate_highcost_risk5/`
- apply combined risk: `data/reports/modeling/20260629_1450_pred_hit_actual_miss_combined_risk/`
- validation combined risk: `data/reports/modeling/20260629_1450_pred_hit_actual_miss_combined_risk_validation/`
- 2025-05 policy compare: `data/reports/backtests/20260629_pred_hit_actual_miss_policy_compare/`
- baseline diagnostics: `data/reports/backtests/20260629_055301_20260629_pred_hit_actual_miss_diag_baseline_stateful_risk5/`
- risk10 diagnostics: `data/reports/backtests/20260629_055301_20260629_pred_hit_actual_miss_diag_failure_only_risk10/`
- combined w1 diagnostics: `data/reports/backtests/20260629_055301_20260629_pred_hit_actual_miss_diag_combined_w1_risk5/`
- risk10 delta: `data/reports/backtests/20260629_055327_20260629_pred_hit_actual_miss_delta_failure_only_risk10/`
- combined w1 delta: `data/reports/backtests/20260629_055327_20260629_pred_hit_actual_miss_delta_combined_w1_risk5/`

## 検証

- `python3 -m unittest tests.test_meta_model tests.test_backtest tests.test_docs_reports`: OK, 124 tests
- `python3 -m trade_data.meta_model oof-trade-failure-model --help`: OK
- `git diff --check`: OK

## 次の作業

1. `pred_hit_actual_miss` をrisk hard penaltyではなく、exit/EV calibration featureとして接続する。
2. `ev_overestimate_high` は分類thresholdではなく連続過大評価量、分位loss、またはtail risk targetへ作り替える。
3. exit timingは `exit_regret_high` 単独分類では弱いため、holding ratio / early close / profit-first失敗とのjoint targetを作る。
4. 採用前に、今回と同じようにOOF validationと未使用月固定外挿の両方で確認する。
