# 自适应传输协议选择实验包说明

这个文件夹用于打包“自适应可靠传输协议选择”实验。内容包括 ns-3
仿真源码、协议横向评测脚本、数据集生成脚本、轻量级机器学习训练脚本、
依赖文件和少量样例结果。

实验目标是：在海底光缆链路场景下，对 TCP CUBIC、TCP BBR 和可选的
QUIC BBR 进行横向评测；再根据实测吞吐率生成标签，训练轻量级模型，
用于在不同链路状态下选择更合适的可靠传输协议。

## 1. 文件夹结构

```text
adaptive-protocol-selection-package/
├── README.md
├── PACKAGE_MANIFEST.md
├── ns3_source/
│   ├── tcp-exp.cc
│   └── quic-random-interval-source.cc
├── protocol_scripts/
│   ├── run-all-protocol-evaluations.py
│   ├── build-protocol-labels.py
│   ├── plot-multidimensional-decision-boundary.py
│   ├── plot-dynamic-link-fluctuation.py
│   ├── dynamic-link-adaptive-protocol.py
│   ├── run-quic-link-grid.py
│   └── merge-quic-into-anchor-labels.py
├── dataset_generators/
│   ├── build-jitter-from-real-anchors.py
│   └── plot-random-interval-continuous-dashboard.py
├── ml_scripts/
│   ├── train-lightweight-protocol-selector.py
│   ├── plot-model-training-performance-summary-png.py
│   └── run-feature-ablation-study.py
├── deployment/
│   └── ml-requirements.txt
└── sample_results/
```

## 2. 环境要求

必须准备：

- Python 3.10-3.13。建议使用 Python 3.13；不建议使用过新的 Python 版本，
  因为部分机器学习依赖可能还没有稳定适配。
- 一个可运行的 ns-3-dev 工程目录，目录下需要有 `./ns3`
- ns-3 支持的 C++ 编译环境

可选准备：

- 外部 ns-3.32 QUIC 工程。只有运行 QUIC BBR 实验时才需要。

先设置路径。`PYTHON` 用于保证“安装依赖”和“运行脚本”使用同一个 Python：

```bash
export PYTHON=python3
export NS3_ROOT=/path/to/ns-3-dev
export PACKAGE_ROOT=/path/to/adaptive-protocol-selection-package
```

安装 Python 依赖：

```bash
cd "$PACKAGE_ROOT"
$PYTHON -m pip install --target python-packages -r deployment/ml-requirements.txt
export PYTHONPATH="$PACKAGE_ROOT/python-packages:$PYTHONPATH"
```

说明：安装依赖和运行脚本必须使用同一个 Python，否则 LightGBM、
XGBoost、CatBoost 等带二进制扩展的包可能出现版本不匹配。

## 3. 复现范围说明

这个包可以完整复现以下内容：

- TCP CUBIC / TCP BBR 的 ns-3 仿真评测。
- random-interval 业务模型下的协议结果采集。
- 标签生成、决策边界绘图、动态链路脚本。
- 基于样例标签数据生成训练样本。
- 轻量级机器学习模型训练和消融实验。

如果要完整复现 TCP CUBIC、TCP BBR、QUIC BBR 三协议对比，还必须额外准备
外部 ns-3.32 QUIC 工程，并设置 `NS3_QUIC_ROOT`。标准 ns-3-dev 本身不包含
本实验使用的 QUIC BBR 模块。

## 4. 准备 ns-3 TCP 仿真程序

把 TCP 仿真源码复制到 ns-3 的 `scratch/` 目录：

```bash
cp "$PACKAGE_ROOT/ns3_source/tcp-exp.cc" "$NS3_ROOT/scratch/tcp-exp.cc"
```

编译：

```bash
cd "$NS3_ROOT"
./ns3 configure --enable-examples --enable-tests
./ns3 build tcp-exp
```

完成后即可运行 TCP CUBIC 和 TCP BBR 相关实验。

## 5. 把协议评测脚本复制到 ns-3

协议评测脚本需要在 `NS3_ROOT` 下运行，因此先复制到
`NS3_ROOT/scratch/`：

```bash
cp "$PACKAGE_ROOT/protocol_scripts/run-all-protocol-evaluations.py" "$NS3_ROOT/scratch/run-all-protocol-evaluations.py"
cp "$PACKAGE_ROOT/protocol_scripts/build-protocol-labels.py" "$NS3_ROOT/scratch/build-protocol-labels.py"
cp "$PACKAGE_ROOT/protocol_scripts/plot-multidimensional-decision-boundary.py" "$NS3_ROOT/scratch/plot-multidimensional-decision-boundary.py"
cp "$PACKAGE_ROOT/protocol_scripts/plot-dynamic-link-fluctuation.py" "$NS3_ROOT/scratch/plot-dynamic-link-fluctuation.py"
cp "$PACKAGE_ROOT/protocol_scripts/dynamic-link-adaptive-protocol.py" "$NS3_ROOT/scratch/dynamic-link-adaptive-protocol.py"
cp "$PACKAGE_ROOT/protocol_scripts/run-quic-link-grid.py" "$NS3_ROOT/scratch/run-quic-link-grid.py"
cp "$PACKAGE_ROOT/protocol_scripts/merge-quic-into-anchor-labels.py" "$NS3_ROOT/scratch/merge-quic-into-anchor-labels.py"
```

## 6. TCP 快速测试

第一次在新机器上运行时，建议先跑这个最小测试。它不依赖 QUIC。

```bash
cd "$NS3_ROOT"
$PYTHON scratch/run-all-protocol-evaluations.py \
  --scenarios=rtt-80:80 \
  --capacities=1 \
  --losses=0.02 \
  --traffic-mode=random-interval \
  --packet-size-ranges=512:1448 \
  --send-interval-ranges=5:20 \
  --file-size-mb=0.05 \
  --duration=2 \
  --output-dir=scratch/adaptive-smoke-tcp-only \
  --skip-quic \
  --no-plot
```

生成标签：

```bash
$PYTHON scratch/build-protocol-labels.py \
  --input=scratch/adaptive-smoke-tcp-only/protocol-evaluation-results.csv \
  --output=scratch/adaptive-smoke-tcp-only/protocol-labels.csv
```

如果生成了 `protocol-evaluation-results.csv` 和 `protocol-labels.csv`，
说明 TCP 部分可以正常运行。

注意：这个快速测试使用 `--skip-quic`，因此标签只在 TCP CUBIC 和 TCP BBR
之间选择最优协议；加入 QUIC 后，标签会在输入结果中实际出现的协议之间选择。

## 7. QUIC 配置

标准 ns-3-dev 中不自带这里使用的 QUIC BBR。若需要运行 QUIC，需要额外
准备外部 ns-3.32 QUIC 工程，并设置：

```bash
export NS3_QUIC_ROOT=/path/to/ns-allinone-3.32/ns-3.32
```

脚本也支持在命令中直接传入：

```bash
--quic-root "$NS3_QUIC_ROOT"
```

期望存在的 QUIC 可执行文件：

- `build/contrib/quic/examples/ns3.32-quic-variants-comparison-bulksend-debug`
- `build/contrib/quic/examples/ns3.32-quic-variants-comparison-random-interval-debug`

如果外部 QUIC 工程中缺少 random-interval 示例，可以参考
`ns3_source/quic-random-interval-source.cc` 添加对应的 QUIC 发包逻辑。

## 8. 完整 random-interval 协议横向评测

以下命令在 `NS3_ROOT` 下运行。

只评测 TCP CUBIC 和 TCP BBR：

```bash
$PYTHON scratch/run-all-protocol-evaluations.py \
  --scenarios=rtt-80:80,rtt-150:150 \
  --capacities=0.2,0.3,0.5,0.75,1,1.5,2,3,4,5 \
  --losses=0.002,0.005,0.01,0.02,0.04,0.06,0.08,0.12,0.16,0.2 \
  --traffic-mode=random-interval \
  --packet-size-ranges=128:512,256:1024,512:1448,1024:2048,1448:4096 \
  --send-interval-ranges=1:5,5:20,20:80,80:200 \
  --file-size-mb=0.2 \
  --duration=1 \
  --output-dir=scratch/real-anchor-grid-4000-random-interval \
  --skip-quic \
  --no-plot \
  --quiet
```

加入 QUIC BBR：

```bash
$PYTHON scratch/run-all-protocol-evaluations.py \
  --scenarios=rtt-80:80,rtt-150:150 \
  --capacities=0.2,0.3,0.5,0.75,1,1.5,2,3,4,5 \
  --losses=0.002,0.005,0.01,0.02,0.04,0.06,0.08,0.12,0.16,0.2 \
  --traffic-mode=random-interval \
  --packet-size-ranges=128:512,256:1024,512:1448,1024:2048,1448:4096 \
  --send-interval-ranges=1:5,5:20,20:80,80:200 \
  --file-size-mb=0.2 \
  --duration=1 \
  --output-dir=scratch/real-anchor-grid-4000-random-interval \
  --quic-root "$NS3_QUIC_ROOT" \
  --no-plot \
  --quiet
```

生成最终协议标签：

```bash
$PYTHON scratch/build-protocol-labels.py \
  --input=scratch/real-anchor-grid-4000-random-interval/protocol-evaluation-results.csv \
  --output=scratch/real-anchor-grid-4000-random-interval/real-anchor-labels-random-interval.csv
```

标签含义：在同一组链路条件和业务负载下，比较 TCP CUBIC、TCP BBR 和
QUIC BBR 的实测吞吐率，把吞吐率最高的协议记为 `best_protocol`。

## 9. 绘制协议决策边界图

可以直接使用包内自带的样例标签文件：

```bash
cd "$PACKAGE_ROOT"
$PYTHON protocol_scripts/plot-multidimensional-decision-boundary.py \
  --input=sample_results/protocol_evaluation/real-anchor-labels-random-interval.csv \
  --output-dir=sample_results/figures
```

主要输出：

- `protocol-decision-boundary-rtt-80ms-clean.png`
- `protocol-decision-boundary-rtt-150ms-clean.png`

这些图用于观察不同 RTT、链路容量、丢包率、包大小和发包间隔下，
哪个协议的吞吐率最高。

## 10. 动态链路实验

在 `NS3_ROOT` 下运行。

TCP-only 版本：

```bash
$PYTHON scratch/dynamic-link-adaptive-protocol.py \
  --output-dir=scratch/dynamic-link-results \
  --scenario-mode=progressive-bad-recover \
  --traffic-mode=random-interval \
  --skip-quic
```

加入 QUIC：

```bash
$PYTHON scratch/dynamic-link-adaptive-protocol.py \
  --output-dir=scratch/dynamic-link-results-with-quic \
  --scenario-mode=progressive-bad-recover \
  --traffic-mode=random-interval \
  --quic-root "$NS3_QUIC_ROOT"
```

这个实验用于模拟链路从正常、逐渐恶化、恶劣波动、逐渐恢复到正常的过程，
并比较静态协议选择和自适应协议选择。

## 11. 构建训练数据

包内已经包含：

- `sample_results/protocol_evaluation/real-anchor-labels-random-interval.csv`
- `sample_results/training_data/jittered-training-samples-12000.csv`

如需从真实锚点标签重新生成带抖动的训练样本：

```bash
cd "$PACKAGE_ROOT"
$PYTHON dataset_generators/build-jitter-from-real-anchors.py \
  --anchor-input=sample_results/protocol_evaluation/real-anchor-labels-random-interval.csv \
  --output-dir=sample_results/training_data \
  --samples=12000
```

这里的 12000 条样本是在真实 ns-3 锚点结果基础上，对链路和业务特征做小范围
扰动得到的训练样本，用于提升模型训练覆盖度。

## 12. 训练轻量级模型

```bash
cd "$PACKAGE_ROOT"
$PYTHON ml_scripts/train-lightweight-protocol-selector.py \
  --input=sample_results/training_data/jittered-training-samples-12000.csv \
  --max-rows=12000 \
  --fast \
  --output-dir=sample_results/model_results
```

生成模型性能汇总图：

```bash
$PYTHON ml_scripts/plot-model-training-performance-summary-png.py \
  --input=sample_results/model_results/model-metrics.csv \
  --output=sample_results/figures/model-training-performance-summary.png
```

主要输出：

- `sample_results/model_results/model-metrics.csv`
- `sample_results/model_results/trained-models.joblib`
- `sample_results/figures/model-training-performance-summary.png`

## 13. 消融实验

```bash
cd "$PACKAGE_ROOT"
$PYTHON ml_scripts/run-feature-ablation-study.py \
  --input=sample_results/training_data/jittered-training-samples-12000.csv \
  --output-dir=sample_results/ablation_results
```

消融实验的作用是：在保持数据、模型、训练测试划分和评估指标不变的情况下，
逐项移除某类特征，观察模型性能下降多少，从而判断该类特征是否重要。

## 14. 常见问题

如果 QUIC 运行失败，先检查：

```bash
export NS3_QUIC_ROOT=/path/to/ns-allinone-3.32/ns-3.32
```

如果暂时不需要 QUIC，可以使用：

```bash
--skip-quic
```

如果 Python 依赖缺失：

```bash
cd "$PACKAGE_ROOT"
$PYTHON -m pip install --target python-packages -r deployment/ml-requirements.txt
export PYTHONPATH="$PACKAGE_ROOT/python-packages:$PYTHONPATH"
```

如果提示找不到 `./ns3`：

```bash
cd "$NS3_ROOT"
```

如果提示找不到 `tcp-exp`：

```bash
cd "$NS3_ROOT"
./ns3 build tcp-exp
```

## 15. 复现步骤清单

- 设置 `NS3_ROOT` 和 `PACKAGE_ROOT`。
- 安装 Python 依赖。
- 把 `tcp-exp.cc` 复制到 `NS3_ROOT/scratch/`。
- 编译 `tcp-exp`。
- 把协议评测脚本复制到 `NS3_ROOT/scratch/`。
- 先运行 TCP 快速测试。
- 可选：设置 `NS3_QUIC_ROOT` 并运行 QUIC 实验。
- 根据协议评测结果生成标签。
- 使用标签数据训练轻量级协议选择模型。
