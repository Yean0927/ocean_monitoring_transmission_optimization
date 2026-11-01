# 第五阶段：Case study

本阶段从旧 04_ablation_experiments/resource_case_study 独立整理，保留真实编解码 CPU 配额控制、网络传输、测量审计及报告生成源码。

- [最终正文与审计说明](reports/README.md)
- `figures/`：资源敏感性及带宽对比的 PNG / PDF / SVG / TIFF。
- `resource-experiment/`：最终 summary、trials、编解码与 CPU 校准摘要和构建记录。大批逐次原始记录在 ocean/raw_experiments/outputs/marine-data-case-study/resource-experiment。
- `figures/layout_figures/`：原论文版式使用的实验图和源数据；论文源码及编译文件已清理。历史名义传输时间版本另放 reports/historical_versions。

在 ocean 根目录，先完成第四阶段 prepared/与必要的 FULL 轨迹，再运行：

```sh
python 05_Case_Study/build_resource_simulator.py
python 05_Case_Study/run_resource_experiment.py --repeats 5
python 05_Case_Study/audit_resource_experiment.py
python 05_Case_Study/build_measured_case_study.py
```

本次只搬运已有结果，没有重新测量。原文件可能包含历史绝对载荷路径；本机通过兼容路径保留可访问性，跨机器重跑须重新准备。资源 CPU 条件是软件配额近似，媒体有损，最终报告保留原有保真和结论边界。
