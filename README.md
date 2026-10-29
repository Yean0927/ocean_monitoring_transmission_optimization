# Ocean 海洋监测实验项目

整理日期：2026-10-26。最终实验代码、输入数据、各阶段报告、报告原图及已有结果统一存放在本目录。报告正文保留原实验结论，只调整存放位置和文件链接。Demo 已移出项目，放在工作区外层的实验代码归档中，不作为交付内容。

## 目录与阅读入口

| 阶段 | 内容 | 报告 |
|---|---|---|
| [01_自适应协议选择](01_自适应协议选择/README.md) | 协议评测、数据集、模型训练、推理与原始图表 | [阶段报告](01_自适应协议选择/reports/README.md) |
| [02_文件压缩](02_文件压缩/README.md) | 文本压缩、视频压缩、弱CPUdocker实验，各自含代码、报告和引用图片 | [阶段报告](02_文件压缩/README.md) |
| [03_缓存机制](03_缓存机制/README.md) | 缓存容量实验、不同优先级实验及共用链路状态 | [阶段报告](03_缓存机制/README.md) |
| [04_消融实验](04_消融实验/README.md) | XGBoost 特征消融、最终八组系统消融与五种子结果 | [阶段报告](04_消融实验/reports/README.md) |
| [05_Case_Study](05_Case_Study/README.md) | 实际编解码和网络资源条件对照 | [阶段报告](05_Case_Study/reports/README.md) |

- [实验报告总索引](实验报告总索引.md)：包括报告、说明、历史版本和论文材料的逐文件入口。
- [报告图片核查与缺失清单](报告图片核查与缺失清单.md)：逐报告核对图片，记录找回来源与缺失项。
- `data/`：原始文本、海流日志、视频及图片输入。
- `shared/`：链路参数生成代码；`third_party/`：最终修复版 QUIC 源码及许可证。
- `文稿与参考材料/`：项目需求 PDF、case study 参考材料与指标说明。论文 LaTeX 源文件和编译结果已清理。
- `原始实验留档/`：原 cache_exam、system-ablation-*、outputs、实验数据、实验报告和 XGBoost 交接目录，保留原始运行与来源文件，避免丢失历史依据。
- `历史版本/`：早期五组系统实验、系数近似联合实验、早期文件缓存模型和旧整理记录，均不与最终实现混用。
- `SOURCE_MANIFEST.json`、`SHA256SUMS.txt`、`CHECKS.md`：来源、文件校验及本次实际验证范围。

## 报告与图片

文件压缩阶段按文本压缩、视频压缩、弱CPUdocker实验分别收录报告，实验代码在各自 code/，报告图片在 images/；缓存阶段同样按容量/优先级两个实验组织，并单独保留共用链路状态；其余阶段继续使用 reports/ 与 assets/。链接均为相对路径。`figures/` 另保留后续图表项目、可编辑 PDF/SVG、PNG/TIFF、源数据与绘图脚本。不同测量日期、旧图近似读数和新实测结果分别保留，未将其合并成同一实验。

原项目目录实际移入 `原始实验留档/`。工作区同名路径仅保留兼容软链接，供已有 ns-3 构建数据库、动态库路径及旧轨迹中的绝对载荷路径使用，不是第二份数据。迁移到新电脑时仍需配置外部工具链并重新准备/编译，不能将这些历史绝对路径视为可迁移配置。

## 环境和运行

```sh
cd /Users/yean/program/海洋监测/ocean
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

已有 joblib 模型优先采用 `04_消融实验/xgboost_features/requirements.txt` 和模型 metadata 记录的依赖版本。视频需要支持相应编码器的 FFmpeg。第一阶段 ns-3 TCP 与独立 ns-3.32 QUIC 工程分别通过 `NS3_ROOT` / `NS3_QUIC_ROOT` 指定。包级缓存、系统消融和 case study 使用 ns-3.42：

```sh
export OCEAN_NS3_ROOT="$PWD/原始实验留档/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42"
export OCEAN_DATA_DIR="$PWD/data"
export OCEAN_IMAGE_DIR="$PWD/data/图片文件"
```

最终系统需将本包 `third_party/quic` 的源码用于对应 ns-3.42 构建，不能把旧公共 QUIC 二进制当作最终修复版。可用 `OCEAN_CACHE_BINARY` / `OCEAN_SYSTEM_BINARY` 显式指定正确构建的程序。正式系统参数、数据保真范围和运行命令见各阶段 README。本次整理不重新训练模型或重跑研究实验。
