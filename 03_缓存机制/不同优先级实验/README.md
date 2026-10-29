# 不同优先级实验

- [包级 ns-3 正式实验报告](实验报告.md)
- [机制说明与早期离散仿真报告](机制说明与离散仿真报告.md)
- [原始实验设计](原始实验设计.md)
- `code/packet_level_cache_priority_experiment.py`、`code/packet-cache-priority.cc`：实际 UDP packet/chunk 级 ns-3 仿真。
- `code/cache_priority_simulation.py`：早期 Python 离散模型，P1–P5 场景，生成率假设共 1.5 Mbps；口径与包级模型分开保留。
- `images/`：正式报告中附带的三张已有结果图；机制报告的链路图共用 ../链路状态/images。

在 ocean 根目录运行：

```sh
python 03_缓存机制/不同优先级实验/code/packet_level_cache_priority_experiment.py --output-dir runs/cache-priority
python 03_缓存机制/不同优先级实验/code/cache_priority_simulation.py --profiles P1 --capacities 50MB --output-dir runs/cache-priority-discrete
```

包级实验需外部 ns-3.42 和正确构建的 packet-cache-priority，配置方式见容量实验。共用 ../链路状态/dynamic-link-fluctuation.csv；可传 --link-csv 或设置 OCEAN_LINK_CSV。

正式包级对照包含 No-Cache、FIFO、Priority-SP、Priority-Aging、Priority-MaxF、Priority-Utility、Priority-Utility-Ti。各策略在同一连续 0–60 min 链路上运行，不在 S1/S2/S3 边界重置缓存。早期 Python 模型包含 Priority-AoI，不能把它当作正式七策略矩阵。

新的原始 CSV、分流统计和本次结果摘要全部写入 output-dir。原先刷新报告的逻辑以本目录实验报告为只读模板，写到输出目录，不改写已整理报告。图中的 S3 送达率与全程尚未丢失比例是不同指标，按各图原注解释。
