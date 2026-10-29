# Corrected QUIC backoff: repeated ablation summary

The QUIC handshake and retransmission timeout multipliers now use exponential backoff (`2^count`) with a 60 s cap, replacing the prior C++ XOR expression. The corrected QUIC library was used for the smoke test and all five repeated seeds (31–35). Each run used the same prepared inputs, a 3600 s observation horizon, and zero drain time. The smoke comparison is recorded separately in `smoke-comparison.csv`.

## Aggregate outcomes

Values are mean ± sample SD across five seeds. Delivery, confirmed loss, and pending percentages are byte-weighted over generated raw-equivalent bytes. Pending means bytes not yet delivered or confirmed dropped by the 3600 s cutoff.

| Variant | Delivered (%) | Confirmed loss (%) | Pending (%) |
|:--|--:|--:|--:|
| FULL | 67.04 ± 42.85 | 23.62 ± 32.34 | 9.34 ± 10.51 |
| WO_PROTOCOL | 62.47 ± 25.16 | 27.33 ± 14.51 | 10.19 ± 10.70 |
| WO_COMPRESSION | 26.56 ± 13.14 | 65.07 ± 14.98 | 8.37 ± 5.00 |
| WO_CACHE | 37.31 ± 27.88 | 61.00 ± 27.86 | 1.69 ± 0.07 |
| BASELINE | 15.21 ± 0.13 | 83.13 ± 0.13 | 1.66 ± 0.00 |
| ADD_PROTOCOL | 21.53 ± 10.76 | 72.43 ± 7.35 | 6.04 ± 5.99 |
| ADD_COMPRESSION | 41.47 ± 14.01 | 54.68 ± 9.12 | 3.85 ± 4.90 |
| ADD_CACHE | 16.57 ± 0.30 | 78.04 ± 0.37 | 5.39 ± 0.12 |

## Interpretation and limits

The corrected QUIC behavior changes results in a configuration-dependent way; it does not improve every QUIC-using ablation. In the repeated runs, FULL has the highest mean delivery rate and lowest mean confirmed-loss rate, while the large standard deviations for FULL and several QUIC variants show substantial seed sensitivity. Report both mean and SD; do not infer statistical significance from these descriptive summaries alone.

The five-seed aggregate files are `summary-across-seeds.csv` (8 overall rows) and `by-stream-across-seeds.csv` (48 rows). Every seed directory contains all eight variants, with an 8-row summary and 48 per-stream rows. Validation found no `QUIC_ABORT`, fatal error, traceback, or error entry in the repeat logs.
