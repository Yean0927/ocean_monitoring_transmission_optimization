# 打包文件清单

这个文件夹用于打包“自适应可靠传输协议选择”阶段的可交付内容，方便
发送给老师、同学或上传 GitHub。

## 已包含内容

### 说明文档

- `README.md`：中文运行说明，包括环境配置、脚本复制、实验命令和常见问题。
- `PACKAGE_MANIFEST.md`：当前打包文件清单。

### ns-3 仿真源码

- `ns3_source/tcp-exp.cc`：主要 TCP 仿真程序。支持 TCP CUBIC、TCP BBR、
  随机包大小和随机发包时间间隔。
- `ns3_source/quic-random-interval-source.cc`：外部 ns-3.32 QUIC
  random-interval 示例的参考源码。

### 协议评测脚本

- `protocol_scripts/run-all-protocol-evaluations.py`：在链路和业务网格上运行
  TCP CUBIC、TCP BBR 和可选 QUIC BBR。
- `protocol_scripts/build-protocol-labels.py`：对同一条件下的协议吞吐率进行
  分组，并生成 `best_protocol` 标签。
- `protocol_scripts/plot-multidimensional-decision-boundary.py`：绘制协议选择
  决策边界图。
- `protocol_scripts/plot-dynamic-link-fluctuation.py`：绘制动态链路波动示意图。
- `protocol_scripts/dynamic-link-adaptive-protocol.py`：评估动态链路下静态协议
  和自适应协议选择效果。
- `protocol_scripts/run-quic-link-grid.py`：单独运行 QUIC 链路网格实验。
- `protocol_scripts/merge-quic-into-anchor-labels.py`：把 QUIC 结果合并进已有
  锚点标签。

### 数据集和机器学习脚本

- `dataset_generators/build-jitter-from-real-anchors.py`：基于真实 ns-3 锚点标签
  生成带抖动的训练样本。
- `dataset_generators/plot-random-interval-continuous-dashboard.py`：绘制
  random-interval 数据集概览图。
- `ml_scripts/train-lightweight-protocol-selector.py`：训练轻量级协议选择模型。
- `ml_scripts/plot-model-training-performance-summary-png.py`：绘制模型性能对比图。
- `ml_scripts/run-feature-ablation-study.py`：运行特征消融实验。

### 依赖文件

- `deployment/ml-requirements.txt`：绘图和模型训练所需的 Python 包。

### 样例结果

- `sample_results/protocol_evaluation/real-anchor-labels-random-interval.csv`：
  已生成的真实锚点标签样例。
- `sample_results/training_data/jittered-training-samples-12000.csv`：
  12000 条带抖动训练样本。
- `sample_results/model_results/model-metrics.csv`：轻量级模型评测指标。
- `sample_results/figures/`：部分展示和检查用图片。

## 未包含内容

- 完整 ns-3-dev 仿真器源码树。
- 外部 ns-3.32 QUIC 工程。
- 本地 Python 虚拟环境或下载后的依赖包目录。
- 可由脚本重新生成的大型中间文件。

## 推荐第一次运行顺序

先按照 `README.md` 第 2-6 节运行 TCP 快速测试；确认 TCP 部分可运行后，
再继续运行完整网格实验、可选 QUIC 实验和机器学习训练。
