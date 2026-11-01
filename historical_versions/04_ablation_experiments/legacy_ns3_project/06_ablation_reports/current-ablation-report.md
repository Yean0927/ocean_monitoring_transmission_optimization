# Current Ablation Report

## Static Protocol Baselines

The current evaluation includes static TCP CUBIC, static TCP BBR, and static QUIC BBR as baselines.

## Adaptive Protocol Selection

Evaluated lightweight models:

- Random Forest
- LightGBM
- XGBoost
- TinyMLP
- CatBoost
- Linear SVM
- Contextual Bandit Ridge

Current 30000-sample training result:

- Best Macro F1: Random Forest, 0.700.
- Best Macro AUC: LightGBM, 0.950.
- Smallest Oracle gap: CatBoost, about 0.021 Mbit/s.

## Compression

LZ4, Gzip, and Gorilla-style compression have been compared separately.

## Integrated Ablation

The integrated leave-one-module-out experiment is complete. It uses:

- XGBoost for adaptive protocol selection; static TCP CUBIC is the ablated baseline.
- The 2 Mbps, unlimited-CPU best compression configuration for each text stream,
  the Host-16C 2 Mbps S1/S2 video decisions, and the JPEG-Q75 image baseline.
- A 50 MB Priority-MaxF cache; No-Cache is the ablated baseline.

See `integrated-ablation-report.md` for the full results and modeling boundary.
