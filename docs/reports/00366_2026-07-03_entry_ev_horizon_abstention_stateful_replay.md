# Entry EV Horizon Abstention Stateful Replay

日時: 2026-07-03 16:02 JST
更新日時: 2026-07-03 16:02 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00365のcandidate rule `lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` を `entry_ev_hold_extension_stateful_replay.py` のextension veto hookへ接続した。
- 00314 w5 hold-extension targetを入力に、one-position constraint、overlap skip、`--require-model-used`、評価倍率 `profit_multiplier=1.0`, `loss_multiplier=1.2` でstateful replayした。
- 広い `all / predicted` では、vetoなしが total `+52.4794`, month min `-324.7062` と崩れるのに対し、同ruleありは total `+267.8748`, month min `-32.9086` まで回復した。
- `refit2025 2025-03` では、`all / predicted / t-5` のvetoなしが `-26.7670`、同ruleありが `+16.0670`。対象月のharmful extensionを止める働きはstatefulでも再現した。
- ただし既存本線の `isolated_large_loss_long / fixed720 / t-5` では、vetoなしが total `+338.4078`, month min `-0.8832` のbestで、同ruleありは全8 extensionsを止めて raw base `+139.1098`, month min `-6.8324` に戻した。
- 判断: extension veto hookとrule実装はaccepted infrastructure。00365 broad ruleは「広域predicted-horizonの安全診断」には有効だが、本線policyのvetoとしては過剰抑制なのでreject。標準policyはNoTrade。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_hold_extension_stateful_replay.py`

Updated tests:

- `tests/test_entry_ev_hold_extension_stateful_replay.py`

Run:

- `data/reports/backtests/20260703_070129_20260703_entry_ev_00366_horizon_abstention_stateful_replay/`

Input:

- `data/reports/backtests/20260702_094645_20260702_entry_ev_00314_fixed60_margin_w5_hold_extension_target_s1/hold_extension_scored_trades.csv`

## Method

New extension veto rule:

```text
lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf =
  selected_loss_first_prob >= 0.40
  OR max(selected_fixed_60m_pred_pnl,
         selected_fixed_240m_pred_pnl,
         selected_fixed_720m_pred_pnl) >= 5.0
  OR (pred_taken_ev >= 5.0 AND selected_loss_first_prob < 0.30)
```

Replay sweep:

```text
apply_universes: all, isolated_large_loss, isolated_large_loss_long
thresholds: -1000000000, -5, 0, 1, 5, 10
horizon_modes: predicted, 720
extension_veto_rules: none, lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf
require_model_used: true
profit_multiplier: 1.0
loss_multiplier: 1.2
```

Important:

- The rule uses only prediction/observable columns already present in scored trades.
- Actual fixed-horizon PnL remains evaluation/teacher only.
- The replay is extension-only stateful: it can lengthen positions and skip overlapping later base trades, but does not create new trades after altered exits.

## Results

Key selection rows:

| universe | threshold | horizon | veto | total | delta vs base | month min | role min | extended | vetoed | skipped | skipped PnL |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `all` | `-5` | `predicted` | none | `+52.4794` | `-86.6304` | `-324.7062` | `-148.4300` | `65` | `0` | `52` | `+4.9216` |
| `all` | `-5` | `predicted` | broad rule | `+267.8748` | `+128.7650` | `-32.9086` | `+6.9988` | `16` | `85` | `15` | `-7.6770` |
| `all` | `5` | `predicted` | none | `+74.1780` | `-64.9318` | `-177.0446` | `-19.0972` | `24` | `0` | `23` | `-3.4016` |
| `all` | `5` | `predicted` | broad rule | `+238.0722` | `+98.9624` | `-32.9086` | `+0.5354` | `6` | `24` | `12` | `-9.7554` |
| `isolated_large_loss_long` | `-5` | `720` | none | `+338.4078` | `+199.2980` | `-0.8832` | `+0.5354` | `8` | `0` | `8` | `-3.9820` |
| `isolated_large_loss_long` | `-5` | `720` | broad rule | `+139.1098` | `+0.0000` | `-6.8324` | `+0.5354` | `0` | `8` | `0` | `+0.0000` |

Target `refit2025 2025-03`:

| universe | threshold | horizon | veto | base | after | delta | trades | extended | vetoed | skipped |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `all` | `-5` | `predicted` | none | `-0.4730` | `-26.7670` | `-26.2940` | `6` | `6` | `0` | `3` |
| `all` | `-5` | `predicted` | broad rule | `-0.4730` | `+16.0670` | `+16.5400` | `9` | `2` | `7` | `0` |
| `isolated_large_loss_long` | `-5` | `720` | none | `-0.4730` | `-0.4730` | `+0.0000` | `9` | `0` | `0` | `0` |

## Failure Analysis

The broad rule blocks all 8 good extensions in the current best `isolated_large_loss_long / t-5 / fixed720` branch.

Those 8 extensions include large positive realized deltas:

| month | base | fixed720 after | delta | triggered component |
|---|---:|---:|---:|---|
| `2025-02` | `-4.5564` | `+7.4500` | `+12.0064` | `loss_first >= 0.40` |
| `2025-04` | `-5.6880` | `+83.8800` | `+89.5680` | `EV >= 5 & loss_first < 0.30` |
| `2025-04` | `-11.7960` | `+2.9700` | `+14.7660` | `loss_first >= 0.40` |
| `2025-06` | `-2.6760` | `+16.7700` | `+19.4460` | `loss_first >= 0.40` |
| `2025-09` | `-3.4680` | `+28.8830` | `+32.3510` | `EV >= 5 & loss_first < 0.30` |
| `2025-10` | `-3.9876` | `+20.8270` | `+24.8146` | `EV >= 5 & loss_first < 0.30` |

Reading:

- 00365のbroad ruleは、`predicted horizon argmax` を広く信じる時の過大延長を止める役割では有効。
- しかし `isolated_large_loss_long / fixed720` は別の構造で、loss-first高値やEV高値がむしろ有益な長時間回復tradeに出ている。
- 同じfeatureを「horizon abstain」へ直接使うと、本線で必要なlong-loss recovery extensionまで止める。

## Decision

Accepted:

- extension veto hookへprediction-based abstention ruleを接続する実装
- `lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` のstateful replay診断
- broad predicted-horizon explorationではabstentionを必ず測る運用

Rejected:

- `lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` を本線hold-extension vetoとして採用すること
- `isolated_large_loss_long / fixed720` branchへ同ruleを重ねること
- 00365のselected-trade counterfactual改善を、そのままone-position policy evidenceと扱うこと

Standard policy remains NoTrade.

## Next

1. horizon abstentionは `all/predicted` のような探索的horizon argmax専用の安全診断として残す。
2. 本線の `isolated_large_loss_long / fixed720` は、loss-first/EV highをriskではなくrecovery signalとして別扱いする。
3. 次はsupport-sufficient negative month向けに、exit abstentionよりreplacement selector / expected PnL calibrationを優先する。
4. もしabstentionを本線へ戻すなら、side/universe/horizon_mode別に学習し、fixed720 long-loss recoveryを保護する制約を入れる。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_hold_extension_stateful_replay.py tests/test_entry_ev_hold_extension_stateful_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_hold_extension_stateful_replay`: OK
- 00366 stateful hold-extension replay: OK
