# Real Anchor Jitter Dataset Summary

Real NS-3 anchors: 3999

Jittered samples: 12000

## Important Note

The anchor table contains real protocol measurements. TCP CUBIC, TCP BBR, and QUIC BBR are measured with the same random packet size and random send interval traffic model. The jittered samples are generated from these real anchors and are not independent NS-3 runs.

The real anchors keep their measured label distribution. By default, the jittered training samples also preserve the anchor-driven label tendency. Use `--balance-labels` only for a separate class-balance ablation experiment.

## Real Anchor Label Distribution

- NO_DELIVERY: 800
- QUIC_BBR: 2220
- TCP_BBR: 551
- TCP_CUBIC: 428

## Jittered Sample Label Distribution

- NO_DELIVERY: 2400
- QUIC_BBR: 6374
- TCP_BBR: 1909
- TCP_CUBIC: 1317

## Scenario Distribution

- rtt-150: 2000
- rtt-80: 1999
