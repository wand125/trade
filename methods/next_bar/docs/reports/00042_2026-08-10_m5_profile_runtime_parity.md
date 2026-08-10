# 00042 M5 Profile runtime parity

日時: 2026-08-10 14:58 JST

## 目的

OOSで採用したM5の `baseline 75% + Intrabar Profile 25%`、baseline方向維持confidenceを最新推論でも同じ式・同じ学習条件で再現する。単体Profile probabilityをblend confidenceとして誤用せず、odds shadowの認可状態も出力へ明示する。

## 実装

`next_bar_ensemble.py` に次を追加した。

- `blend_probability_values`: OOSとruntimeで共有する唯一のblend関数。
- `assert_latest_artifact_parity`: split境界と主要学習設定を照合するguard。
- `blend_latest_prediction_frames`: 時間足、bar start、decision timestampが完全一致した最新予測だけをblendする。
- `predict_latest_ensemble`: 2つの保存artifactから最新予測、blend、context policy、odds診断を一続きで実行する。
- `predict_latest_ensemble.py`: 上記runtime経路のCLI。

artifact parity guardは次を一致必須にする。

- train/calibration/test境界。
- flat tolerance、最大train行、random seed。
- HGB iteration、learning rate、leaf、min samples、L2。
- confidence model、probability calibration。
- train weighting/filter、model type、training window。

feature setだけはbaselineとintrabar_profileで意図的に異なる。既存 `deployment_candidate_001` は明示日付境界、Profile最新artifactは60/20/20境界だったためguardで不適合と判定し、混合しなかった。Profileと同一条件の `baseline_m5_latest_artifact_001` を新規学習した。

## OOS/runtime共通式

通常blendは次式である。

```text
p_blend = 0.75 * p_baseline + 0.25 * p_profile
```

方向維持時はbaseline方向へ射影し、blend edgeが反対側へ出た場合はbaseline方向の0.5直上/直下へ留める。OOSの `blend_prediction_frames` もruntimeも `blend_probability_values` を呼ぶため、別実装によるずれを排除した。

配列の共通式一致、方向維持、時刻不一致拒否、split不一致拒否、odds認可抑止を単体テストした。

## 実データ最新推論

判定時刻は2026-06-01 04:55 UTC。

| item | value |
|---|---:|
| baseline probability up | 0.5332709162 |
| Profile probability up | 0.5314733746 |
| 75/25 blended probability up | 0.5328215308 |
| predicted direction | up |
| direct formulaとの差 | 1.11e-16 |
| empirical local accuracy | 0.5323907243 |
| local Wilson interval | 0.5241659256–0.5405979575 |
| local support | 13,664 |

blend confidenceは履歴の局所Wilson区間内で、下限も50%を超えた。0.515 shadow policyも通過した。

## Shadow認可ゲート

統計calibration gateと運用認可を分離した。

- `odds_calibration_gate_passed=true`: 履歴上のglobal/local校正条件を満たす。
- `odds_runtime_authorized=false`: 完全未使用期間でまだ昇格していない。
- `odds_valid=false`: 上の2条件のANDなのでshadowではfalse。
- `strict_prediction_eligible=false`: odds未認可なのでfalse。

CLIで `--authorize-odds` を明示した場合だけ、calibration gateを通る行の `odds_valid` をtrueにできる。現在の固定コマンドにはこのflagを付けない。

## 再現コマンド

```bash
uv run python methods/next_bar/scripts/predict_latest_ensemble.py \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --baseline-model-dir experiments/next_bar/baseline_m5_latest_artifact_001 \
  --candidate-model-dir experiments/next_bar/intrabar_profile_m5_latest_artifact_001 \
  --candidate-weight 0.25 \
  --preserve-baseline-direction \
  --context-policy methods/next_bar/config/m5_intrabar_profile_runtime_shadow_policy_v1.json \
  --odds-calibration experiments/next_bar/intrabar_profile_m5_odds_calibration.json \
  --output experiments/next_bar/intrabar_profile_m5_latest_ensemble_001/latest_prediction.json \
  --parity-output experiments/next_bar/intrabar_profile_m5_latest_ensemble_001/parity.json
```

## 成果物と判断

- baseline latest artifact: `experiments/next_bar/baseline_m5_latest_artifact_001`
- Profile latest artifact: `experiments/next_bar/intrabar_profile_m5_latest_artifact_001`
- runtime output: `experiments/next_bar/intrabar_profile_m5_latest_ensemble_001/latest_prediction.json`
- parity manifest: `experiments/next_bar/intrabar_profile_m5_latest_ensemble_001/parity.json`
- shadow policy: `methods/next_bar/config/m5_intrabar_profile_runtime_shadow_policy_v1.json`

runtime blend parity条件は達成したため、odds shadowの未達条件から外す。ただしこれは実装一致の確認であり、予測edgeの新規証拠ではない。fresh期間未検証のためauthoritative confidence、fair odds、paper policyは変更せず、runtime shadowだけを有効にする。損失倍率は標準1.0のみとする。
