# 0007: High-turnover validation gateを2025-07 blind前に固定する

日付: 2026-06-28 11:14 JST
状態: accepted

## 背景

2025-06 blindで、`short:session_regime=asia` block候補は `short:london` に損失を移しただけだった。session hard blockを増やすとNoTradeに近づくため、次の未見月を見る前に、validation側で short exposure、direction/session損失、support-aware miss/calibrationを使った選定基準を固定する必要がある。

前回候補周辺gridは月10trades条件を満たせなかった。一方、`min_entry_rank=0/0.5`, `max_wait_regret=4/inf`, `profit_barrier_threshold=0.0/0.2` を含む high-turnover gridでは、validation 4ヶ月で候補が残った。

詳細は `docs/reports/00028_2026-06-28_high_turnover_gate_validation.md`。

## 決定

2025-07 blindを見る前の暫定選定基準を以下に固定する。

- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- cost-aware validation: spread `0.1`, slippage `0.05`, delay `0`
- `min-trades-per-fold=10`
- `max-forced-exit-rate=0.05`
- `max-drawdown=100`
- `min-base-adjusted-pnl-per-fold=0`
- `min-cost-adjusted-pnl-per-fold=0`
- `max-side-loss-per-fold=100`
- `max-direction-session-loss-per-fold=60`
- `max-short-trade-share=0.65`
- `max-smoothed-actual-profit-barrier-miss-rate=0.55`
- smoothed profit barrier calibrationはhard gateにしない

暫定候補Aを次の未見月評価の主候補にする。

- policy: `fixed_horizon_ev`
- entry threshold: `0`
- long entry threshold offset: `0`
- short entry threshold offset: `8`
- exit threshold: `0`
- side margin: `1`
- risk penalty: `0`
- max wait regret: `4`
- min entry rank: `0.5`
- require profit barrier: yes
- profit barrier threshold: `0.0`
- extra side margin rules: `session_regime=asia:5,session_regime=rollover:5`
- side block rules: none

## 影響

- 2025-07以降のblind評価では、この基準と候補Aを先に固定してから結果を見る。
- 2025-06は既に見た月なので、候補Aの2025-06成績は採用根拠ではなく回帰チェックとしてだけ扱う。
- smoothed calibrationは、候補の説明・tie-break・失敗分析には使うが、現時点ではhard gateにしない。
- profit barrier threshold `0.0` が選ばれたことは、barrier probability targetの選別力が弱い兆候として別途分析する。

## 2025-07 Blind結果

更新日時: 2026-06-28 12:27 JST

このdecisionは「2025-07を見る前の選定基準を固定した」記録として維持するが、候補A自体は2025-07 blindで失敗した。

- no-cost adjusted pnl: `+1.5838`
- standard cost-aware adjusted pnl: `-12.7764`
- trades: `66`
- profit factor: `0.9049`
- short trade share: `0.0758`
- worst direction/session: `long:ny_overlap`

short concentrationは回避できたが、edgeが薄く、損失は long / `ny_overlap` / `low_vol` / `down_low_vol` に移った。候補Aは採用候補から外し、次の候補選定ではcost-aware評価を主目的へ寄せる。

詳細は `docs/reports/00029_2026-06-28_blind_2025_07_candidate_a.md`。

## 代替案

- `max-forced-exit-rate=0`: validation候補が全滅した。24h強制決済は仕様上あり得るため、現段階では厳しすぎる。
- `max-direction-session-loss-per-fold=45`: validation候補が全滅した。暫定的に `60` とする。
- smoothed calibration hard gate `0.60`: validationでは1候補に絞れるが、2025-06既知月でLondon short崩れを再発する候補を選んだため採用しない。
- `short:session_regime=asia` block候補: 2025-06での失敗履歴があり、今回のcalibration hard gateでも危険な方向へ寄ったため、主候補にしない。
