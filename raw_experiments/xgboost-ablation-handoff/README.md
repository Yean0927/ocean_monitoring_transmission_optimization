# XGBoost 协议选择模型与消融交接包

## 1. 这是什么模型

用于海底光缆链路协议选择的 XGBoost 三分类模型，输入链路和业务特征，输出 `TCP_CUBIC`、`TCP_BBR` 或 `QUIC_BBR`。这里的“权重”是训练后的提升树集合，不是神经网络权重矩阵。

采用二阶段精调选出的参数：`learning_rate=0.04`、`n_estimators=220`、`max_depth=11`，另固定 `subsample=0.85`、`colsample_bytree=0.85`、`random_state=42`。本次导出限制为 4 个 CPU 线程，原脚本使用 `n_jobs=-1`。

**来源说明：原精调脚本保存了指标，但没有保存模型。本包是按原数据、原随机划分和原参数重新训练导出的版本，不是找回的历史权重。** 已核对指标，差异仅为浮点舍入量级；没有重新搜索参数。

| 原报告口径的核对指标 | 本次复现 |
| --- | ---: |
| Accuracy | 0.883333 |
| Macro F1 | 0.811838 |
| Macro AUC（OvR） | 0.965505 |
| 平均选择吞吐率 | 0.479348 Mbit/s |
| Oracle 吞吐率 | 0.492630 Mbit/s |
| Oracle gap | 0.013281 Mbit/s |

这些是历史样本行随机划分的结果，**不代表独立锚点上的泛化性能**。

## 2. 文件怎么用

| 文件 | 用途 |
| --- | --- |
| `model/xgboost.json` | 复现原报告的 XGBoost 原生模型文件 |
| `model/preprocessor.joblib` | 配套标准化及类别独热编码，加载 JSON 时必须配套使用 |
| `model/pipeline.joblib` | 同一模型的完整 sklearn Pipeline，已包含预处理 |
| `model/metadata.json` | 参数、类别编号、原始/变换后特征顺序、版本、指标及数据 SHA256 |
| `model/split.csv` | 原报告复现使用的训练/测试样本编号及顺序 |
| `data/jittered-training-samples-12000.csv` | 消融重训练使用的完整扩展数据 |
| `data/real-anchors-4000.csv` | 锚点来源表，实际为 3999 条，文件名沿用历史名称 |
| `data/dataset-summary.md` | 原始数据构成说明 |
| `example-input.csv` | 可直接推理的 8 行输入示例 |
| `run.py` | 导出、校验、推理、消融实验统一入口 |
| `results/anchor/` | 已跑通的锚点分组消融结果、每个变体的模型及同一份划分 |
| `provenance/` | 原评测脚本、原训练脚本和历史指标，仅作溯源，不是本包运行入口 |

**给别人发整个 ZIP，不要只发 JSON。** 原模型接收的是预处理后的 31 维输入，而不是直接接收 28 个原始字段。不要漏掉预处理器或自行改变特征顺序。

## 3. 环境与操作顺序

本机验证环境：Python 3.13.11；依赖版本见 `requirements.txt`。建议使用 Python 3.13 创建独立环境。本包不需要安装 NS-3、LightGBM 或 CatBoost，也不需要重新生成仿真数据。

解压后进入本文件所在目录，在终端执行：

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py verify
python run.py predict
python run.py ablate
```

Windows 将激活命令换为 `.venv\Scripts\activate`。macOS 如果 XGBoost 提示缺少 `libomp.dylib`，使用 Homebrew 安装 `libomp`；Linux 如缺少 `libgomp.so.1`，安装系统的 OpenMP 运行库。不同系统的安装过程尚未逐一验证。

- `verify`：校验数据 SHA256、JSON 与 Pipeline 预测一致性，以及原报告测试划分上的导出指标。
- `predict`：默认读取 `example-input.csv`，在包内生成 `predictions.csv`，包含三个协议的概率和预测协议。
- `ablate`：默认按 `anchor_id` 分组，训练每个消融变体，写入 `results/anchor/`；重复运行会更新该目录的同名结果。

指定自己的完整特征输入：

```bash
python run.py predict --input my-features.csv --output my-predictions.csv
```

只跑完整模型和一个消融项：

```bash
python run.py ablate --variants full no_send_interval
```

注意：该命令的指标 CSV 只包含本次选择的变体。重新跑全部变体，直接运行 `python run.py ablate`。

仅为复现历史口径，才使用：

```bash
python run.py ablate --split legacy-row
```

`python run.py export` 会重新训练并覆盖 `model/`；通常无需执行，因为模型已经导出。

## 4. 加载模型

推荐直接使用完整 Pipeline：

```python
import json
from pathlib import Path
import joblib
import pandas as pd
from run import normalize

root = Path(".")  # 当前目录是解压后的交接包
meta = json.loads((root / "model/metadata.json").read_text())
features = meta["numeric_features"] + meta["categorical_features"]
model = joblib.load(root / "model/pipeline.joblib")
inputs = normalize(pd.read_csv(root / "example-input.csv"))
indices = model.predict(inputs[features]).astype(int)
protocols = [meta["class_mapping"][str(i)] for i in indices]
print(protocols)
```

编号是 `0=QUIC_BBR`、`1=TCP_BBR`、`2=TCP_CUBIC`，不能按其他展示顺序解释概率列。只加载可信来源的 joblib 文件；不建议跨 sklearn 版本加载。

## 5. 消融怎样严格对照

**删掉特征后必须重新训练，不能直接给已有模型少传几列，也不能把置零当成重新训练消融。** 本包六个变体使用同一训练/测试划分、同一组超参数、同一随机种子，预处理器仅在训练集拟合；不对各变体单独调参。

| 变体 | 去除内容 |
| --- | --- |
| `full` | 不去除，共 28 个原始输入字段 |
| `no_packet_size` | 包大小 min/max/mean/std，同时去除派生的 offered load |
| `no_send_interval` | 间隔 min/max/mean/std、interval_mode，同时去除 offered load |
| `no_traffic` | 包大小、间隔、负载、文件大小、压缩比例及业务类别 |
| `no_context` | 阶段/趋势、前一状态、场景类别及前一协议 |
| `link_only` | 只保留 RTT、capacity、packet loss rate |

`offered_load_mbps` 同时关联包大小和发送间隔，所以相关消融中一并删除，避免保留直接派生信息。具体移除列表在 `run.py` 的 `VARIANTS` 中，每个变体的保留特征也单独保存为 JSON。

已经运行的默认分组消融（7199 行训练、2401 行测试，锚点交集为 0）：

| 变体 | Macro F1 | Macro AUC | 平均选择吞吐率 Mbit/s | Oracle gap Mbit/s |
| --- | ---: | ---: | ---: | ---: |
| 完整模型 | 0.7932 | 0.9565 | 0.4351 | 0.0161 |
| 去包大小 | 0.7073 | 0.9207 | 0.4200 | 0.0313 |
| 去发包间隔 | 0.4503 | 0.7460 | 0.3658 | 0.0854 |
| 去业务特征 | 0.4279 | 0.7067 | 0.3625 | 0.0887 |
| 去历史/场景上下文 | 0.7858 | 0.9546 | 0.4348 | 0.0165 |
| 仅链路三项 | 0.4323 | 0.7134 | 0.3618 | 0.0894 |

本次分组完整模型为 `results/anchor/full-pipeline.joblib`（也提供 `full.json`）。如果对方要在本次消融结果上继续工作，应使用这里的完整模型作基线，而不是直接套用 `model/` 中历史划分的指标。两者测试集不同，吞吐率数值不能直接比较来判断模型退步。

## 6. 数据与结论边界

- 数据来自 3999 个实测锚点扩展出的 12000 条抖动样本；扩展行不是独立 NS-3 实测，扩展吞吐率也不能称为逐条真实重测。
- 排除 2400 条 `NO_DELIVERY` 后，三分类使用 9600 行。历史划分为 7200/2400。模型没有“全部不可交付”这一输出类别，不适用于断连检测。
- 原行随机划分中，训练/测试共有 1780 个重复出现的锚点 ID；因此默认消融改用锚点分组。历史指标只用于复现，不作为无泄漏泛化结果。
- 分组测试仍属于已有扩展数据上的离线评估；历史调参可能已经接触过这些数据。正式独立结论还需新的未参与调参的锚点、多个分组种子或嵌套交叉验证。
- 三个吞吐率字段和 `best_protocol` 仅用于标签/评估，不作为输入特征。Oracle 是逐行三个吞吐率的最大值，再取平均，不是可部署模型。
- 若一个字段在数据中恒定或由其他字段复制，其消融不能证明该机制无用。额外的趋势/历史字段也不能自动解释为真实在线观测。
- 本包用于协议选择模型的特征消融，不包含压缩、缓存或实际协议在线切换的系统级消融，也不重新运行 NS-3。

已在本机验证：完整模型导出、原记录指标核对、模型加载推理、全部六组分组消融。软件版本与数据校验值见 `model/metadata.json`。
