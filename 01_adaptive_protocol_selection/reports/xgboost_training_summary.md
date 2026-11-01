# Lightweight Protocol Selector Training Results

Training samples: 9000

Test samples: 3000

Max rows setting: 30000

## Best models

- Best Macro F1: XGBoost (0.880)
- Best average selected throughput: XGBoost (0.446 Mbit/s)

## Metrics

| Model | Accuracy | Macro F1 | Macro AUC | Weighted AUC | Macro Precision | Macro Recall | Avg selected Mbit/s | Oracle gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| XGBoost | 0.909 | 0.880 | 0.983 | 0.986 | 0.880 | 0.881 | 0.446 | 0.008 |

Note: AUC is computed with multiclass one-vs-rest. Oracle is the theoretical upper bound that selects the best protocol for every test sample. A smaller Oracle gap means the selector is closer to the optimal choice.
