# 第一阶段：协议自适应选择

保留最终主训练、协议评测、标签生成、扰动样本生成、模型与原始训练数据。`train-lightweight-protocol-selector.py` 是主训练入口；sync 副本和旧特征消融保留其原文件名以便溯源。最终 XGBoost 分组特征消融在第四阶段。

- [实验报告与说明](reports/README.md)
- `figures/原始阶段图表/`：原决策边界、训练性能和链路图。
- `figures/模型性能对比/`：后续性能图、源数据及绘图脚本。

在 ocean 根目录运行，脚本的相对输入输出参数以阶段目录为基准：

```sh
python 01_自适应协议选择/dataset_generators/build-jitter-from-real-anchors.py --samples 12000 --output-dir sample_results/training_data_new
python 01_自适应协议选择/ml_scripts/train-lightweight-protocol-selector.py --max-rows 12000 --fast --output-dir sample_results/model_results_new
```

实际协议仿真需要设置 `NS3_ROOT` / `NS3_QUIC_ROOT` 并编译 `ns3_source/` 对应示例。其 TCP/QUIC 构建名称和历史模型对照参数见 reports/协议自适应选择实验说明.md。恢复的原绘图脚本可能仍使用原工程的输入布局，已有最终图表已随包收录。
