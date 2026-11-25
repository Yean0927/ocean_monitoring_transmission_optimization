# 不同优先级实验

- [包级 ns-3 正式实验报告](experiment_report.md)
- [机制说明与早期离散仿真报告](mechanism_and_discrete_simulation_report.md)
- [原始实验设计](original_experiment_design.md)
- `code/packet_level_cache_priority_experiment.py`、`code/packet-cache-priority.cc`：实际 UDP packet/chunk 级 ns-3 仿真。
- `code/cache_priority_simulation.py`：早期 Python 离散模型，P1–P5 场景，生成率假设共 1.5 Mbps；口径与包级模型分开保留。
- `images/`：正式报告中附带的三张已有结果图；机制报告的链路图共用 ../link_conditions/images。

在 ocean 根目录运行：

```sh
python 03_cache_mechanism/priority_experiments/code/packet_level_cache_priority_experiment.py --output-dir runs/cache-priority
python 03_cache_mechanism/priority_experiments/code/cache_priority_simulation.py --profiles P1 --capacities 50MB --output-dir runs/cache-priority-discrete
```

包级实验需外部 ns-3.42 和正确构建的 packet-cache-priority，配置方式见容量实验。共用 ../link_conditions/dynamic-link-fluctuation.csv；可传 --link-csv 或设置 OCEAN_LINK_CSV。

正式包级对照包含 No-Cache、FIFO、Priority-SP、Priority-Aging、Priority-MaxF、Priority-Utility、Priority-Utility-Ti。各策略在同一连续 0–60 min 链路上运行，不在 S1/S2/S3 边界重置缓存。早期 Python 模型包含 Priority-AoI，不能把它当作正式七策略矩阵。

当前入口默认每秒生成 208,481 B 的 V1 视频数据，拆成最多 1472 B 的数据块，在该秒内按字节速率逐包产生。新运行的原始 CSV、分流统计和结果摘要写入 `--output-dir`。
