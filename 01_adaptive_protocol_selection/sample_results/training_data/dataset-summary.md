# Real Anchor Jitter Dataset Summary

Real NS-3 anchors: 4000

Jittered samples: 12000

## Important Note

The anchor table contains real protocol measurements. TCP CUBIC and TCP BBR are measured with random packet size and random send interval. QUIC BBR is measured on the same RTT/capacity/loss link conditions with the external ns-3.32 QUIC bulk-send example. The jittered samples are generated from these real anchors and are not independent NS-3 runs.

The real anchors keep their measured label distribution. By default, the jittered training samples also preserve the anchor-driven label tendency. Use `--balance-labels` only for a separate class-balance ablation experiment.

## Real Anchor Label Distribution

- QUIC_BBR: 1910
- TCP_BBR: 530
- TCP_CUBIC: 1560

## Jittered Sample Label Distribution

- QUIC_BBR: 5729
- TCP_BBR: 2053
- TCP_CUBIC: 4218

## Scenario Distribution

- rtt-150: 2000
- rtt-80: 2000
