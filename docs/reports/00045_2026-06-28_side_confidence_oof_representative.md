# Side Confidence Representative OOF

日時: 2026-06-28 17:12 JST
更新日時: 2026-06-28 17:12 JST

## Summary

- Experiment ID: `20260628_081124_best_side_oof_representative_smoke`
- Diagnostic ID: `20260628_081219_side_confidence_oof_representative_smoke`
- Status: diagnostic only, not a tradable candidate
- Main result: representative 4-month blocked OOF shows global side-confidence calibration is much better than the prior valid/test smoke, but regime-level overconfidence remains.
- Report numbering note: this file is numbered from the internal `日時`, not filesystem mtime or `更新日時`.

## Why

The prior `best_side` smoke showed that a global `min_side_confidence` gate can select confidently wrong trades. To check whether this was just one test split artifact, we generated OOF predictions over representative validation months and ran `side-confidence-report`.

## Data

- Dataset: `data/processed/datasets/xauusd_m1_best_side_oof_smoke/`
- Generated months: 2024-07 to 2025-01
- OOF months: 2024-07, 2024-09, 2024-11, 2025-01
- PnL adjustment: profit `1.0`, loss `1.20`
- Edge: `15`
- Purge / embargo: enabled, 24h embargo

The initial attempt to run full 7-month `target-set policy` OOF was too heavy for a diagnostic iteration. We added a lighter `side_confidence` target set and used representative months.

## Model Setup

- Target set: `side_confidence`
- Regression targets:
  - `long_best_adjusted_pnl`
  - `short_best_adjusted_pnl`
- Classification targets:
  - `best_side`
- Max iter: `20`
- Sample frac: `0.25`
- Sample weighting: `month_label`

This is a smoke/diagnostic model. It is not a production model or executable policy candidate.

## OOF Metrics

| metric | value |
|---|---:|
| rows | 119,241 |
| best_side accuracy | 0.5666 |
| best_side balanced accuracy | 0.5519 |
| best_side macro f1 | 0.5517 |
| long EV R2 | 0.0607 |
| short EV R2 | -0.0235 |

## Side Confidence Calibration

Overall OOF:

| rows | accuracy | balanced accuracy | confidence mean | overconfidence | predicted long share | actual long share |
|---:|---:|---:|---:|---:|---:|---:|
| 119,241 | 0.5666 | 0.5519 | 0.5685 | 0.0020 | 0.5882 | 0.5938 |

This is globally much better calibrated than the prior valid/test smoke.

Month-level:

| month | rows | accuracy | confidence mean | overconfidence | note |
|---|---:|---:|---:|---:|---|
| 2024-07 | 31,587 | 0.5777 | 0.5638 | 0.0000 | slightly underconfident |
| 2024-09 | 28,885 | 0.5071 | 0.5810 | 0.0739 | weak month |
| 2024-11 | 28,572 | 0.5390 | 0.5706 | 0.0316 | mild overconfidence |
| 2025-01 | 30,197 | 0.6379 | 0.5596 | 0.0000 | underconfident |

Worst regime groups:

| group | rows | accuracy | confidence | overconfidence | predicted long share | actual long share |
|---|---:|---:|---:|---:|---:|---:|
| `high_vol` | 503 | 0.4553 | 0.5949 | 0.1396 | 0.6282 | 0.3499 |
| `down_normal_vol` | 7,830 | 0.4764 | 0.5865 | 0.1101 | 0.5741 | 0.5250 |
| `up_normal_vol` | 7,210 | 0.4656 | 0.5485 | 0.0829 | 0.4445 | 0.5628 |
| `2024-09` | 28,885 | 0.5071 | 0.5810 | 0.0739 | 0.5492 | 0.5875 |
| `normal_vol` | 27,408 | 0.5080 | 0.5647 | 0.0567 | 0.5733 | 0.5574 |

Confidence buckets:

| bucket | rows | accuracy | confidence | overconfidence |
|---|---:|---:|---:|---:|
| 0.50-0.60 | 92,751 | 0.5763 | 0.5480 | 0.0000 |
| 0.60-0.70 | 24,057 | 0.5528 | 0.6327 | 0.0799 |
| 0.70-0.80 | 2,433 | 0.3309 | 0.7191 | 0.3882 |

## Findings

- The classifier is not globally broken: OOF overall accuracy and confidence nearly match.
- High-confidence bins are still dangerous. The 0.70-0.80 bucket is strongly overconfident and below random.
- Regime matters more than global calibration. `normal_vol` combined regimes and the small `high_vol` slice remain unstable.
- `2025-01` is underconfident, while `2024-09` is overconfident. A single global confidence threshold would treat these poorly.
- `side_confidence` target set is useful for fast OOF diagnostics. It avoids training the full policy target list when the question is only side calibration.

## Next Actions

- Do not adopt a global `min_side_confidence` hard gate.
- Use OOF diagnostics to design a regime-aware side-confidence penalty or calibration layer.
- Re-run the representative OOF with more fit data or lower learning rate before using the signal in executable backtests.
- If high-confidence overfit persists, consider explicitly penalizing high confidence in unstable regimes rather than rewarding it.
