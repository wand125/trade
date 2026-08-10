# 00056 Paired daily block bootstrap and subgroup audit

日時: 2026-08-10 17:31 JST

## 目的

Intrabar Distribution Shape 0.53はregistryの点推定objectiveでselective championになったが、Extra Treesとの差は小さい。連続M15足を独立標本として扱うだけでは不確実性を過小評価し得るため、日中の系列依存を保つUTC日単位paired block bootstrapで差の区間を測る。

## 方法

- 各UTC日を1 blockとし、同じ日indexを2候補へpairedで復元抽出する。
- development 1,226日、confirmation 752日、all 1,978日を各5,000回再標本化する。
- 固定confidence 0.53のaccuracy、coverage、Wilson下限、selection scoreと、全行Brier/log lossを再計算する。
- deltaは常にDistribution minus comparator。accuracy/coverage/Wilson/scoreは正、Brier/log lossは負がDistribution優位である。
- seed 42、現在/future値を使う学習やparameter探索はない。

実装は `src/trade_data/next_bar_bootstrap.py`、CLIは `methods/next_bar/scripts/bootstrap_fixed_candidates.py`。日block分離、paired alignment、seed再現性を単体テストした。

## Extra Trees 0.53との結果

| period / metric | point delta | paired day-bootstrap 95% CI | Distribution優位確率 |
|---|---:|---:|---:|
| development accuracy | +0.108pt | -0.123〜+0.347pt | 82.0% |
| development selection score | +0.000475 | -0.000773〜+0.001775 | 77.6% |
| confirmation accuracy | -0.113pt | -0.531〜+0.271pt | 27.4% |
| confirmation selection score | -0.000620 | -0.002384〜+0.001030 | 22.5% |
| all accuracy | +0.046pt | -0.158〜+0.254pt | 66.5% |
| all selection score | +0.000112 | -0.000910〜+0.001150 | 57.7% |
| all Brier | -0.00000854 | -0.00002592〜+0.00000885 | 82.9% |
| all log loss | -0.00001717 | -0.00005221〜+0.00001787 | 82.9% |

点推定ではdevelopment/allでDistributionが上だが、全metricの95%区間が0を跨いだ。Extra Treesへの統計的優位は確認できない。coverage差は全期間で確実に負で、Distributionは約0.25pt少ない選択集合である。

## 正式baseline 0.53との結果

| period / metric | point delta | paired day-bootstrap 95% CI | 判定 |
|---|---:|---:|---|
| development accuracy | +0.266pt | +0.035〜+0.501pt | 支持 |
| development selection score | +0.001138 | -0.000123〜+0.002415 | 未確定 |
| development Brier | -0.00005114 | -0.00007578〜-0.00002537 | 支持 |
| confirmation accuracy | +0.071pt | -0.283〜+0.431pt | 未確定 |
| confirmation selection score | +0.000016 | -0.001503〜+0.001541 | 未確定 |
| all accuracy | +0.212pt | +0.017〜+0.411pt | 支持 |
| all selection score | +0.000762 | -0.000219〜+0.001754 | 未確定 |
| all Brier | -0.00003898 | -0.00005707〜-0.00002170 | 支持 |

baselineに対してはdevelopment/allのaccuracyとBrier/log loss改善が日block後も残った。一方、coverageを含む主selection scoreとconfirmation単独は区間が0を跨ぐ。forward candidateとしての根拠はあるが、aggregate confirmationの微差だけでauthoritativeへ昇格できる強さではない。

## Fixed subgroup audit

confirmationの0.53 laneをpredicted direction × volatility regimeの固定6セルで監査した。

| cell | rows | accuracy | mean confidence | Wilson lower | local/edge |
|---|---:|---:|---:|---:|---|
| up-high | 5,011 | 55.258% | 54.260% | 53.878% | yes/yes |
| up-normal | 1,890 | 54.286% | 54.104% | 52.033% | yes/yes |
| up-low | 629 | 55.803% | 53.986% | 51.898% | yes/yes |
| down-high | 1,223 | 55.437% | 53.824% | 52.639% | yes/yes |
| down-low | 419 | 52.267% | 53.857% | 47.486% | yes/no |
| down-normal | 859 | 49.942% | 53.817% | 46.606% | no/no |

down-normalは実accuracyが50%未満で、mean confidenceもWilson区間外だった。Extra Treesもdown-low/normalでWilson edgeを通らないが、down-normalはaccuracy 50.893%で局所整合は通った。Distribution固有のconfirmation overconfidenceとしてfresh期間で必ず再監査する。

この区分は結果後に診断したため、down-normalを除外するpost-hoc gateにはしない。

## 判断

Distribution 0.53のregistry championは、事前固定のpoint objective規定に基づく「履歴上のchampion」として維持する。ただしbootstrapはExtra Trees置換を支持せず、subgroupにも弱点がある。運用上はExtra Treesと同格のparallel forward候補として扱い、fresh期間で次をすべて満たすまでauthoritative confidenceへ昇格しない。

- 0.53 accuracy・selection score・BrierがExtra Trees以上
- down-normalが局所整合し、down-low/normalに重大な劣化がない
- baselineに対するconfirmation selection score差が正

成果物は `experiments/next_bar/intrabar_distribution_shape_vs_extra_trees_m15_053_daily_bootstrap.json`、`intrabar_distribution_shape_vs_baseline_m15_053_daily_bootstrap.json`、`intrabar_distribution_shape_m15_053_subgroup_reliability.json` に保存した。

