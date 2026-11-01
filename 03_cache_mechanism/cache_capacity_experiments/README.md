# 缓存容量实验

- [实验报告](experiment_report.md)：连续 0–60 min、FIFO 固定策略，10 MB 粒度扫描的历史结果，最小充足容量 120 MB。
- `code/fifo_cache_capacity_experiment.py`：实际调用 ns-3 的容量扫描入口。
- `code/packet-cache-priority.cc`：该入口使用的包级缓存核心。
- `images/`：报告附带的既有容量结果图。

链路输入共用 ../link_conditions/dynamic-link-fluctuation.csv。以下命令在 ocean 根目录运行：

```sh
export OCEAN_NS3_ROOT="$PWD/raw_experiments/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42"
python 03_cache_mechanism/cache_capacity_experiments/code/fifo_cache_capacity_experiment.py --step-mb 10 --max-mb 400 --output-dir runs/cache-capacity
```

ns-3 工程需编译 scratch/packet-cache-priority.cc，默认构建产物 build/scratch/ns3.42-packet-cache-priority-optimized。可用 OCEAN_CACHE_BINARY 覆盖；链路可用 --link-csv 或 OCEAN_LINK_CSV 覆盖。新 CSV、逐档原始结果和运行摘要写入 output-dir，不覆盖本目录报告。充足判定是无缓存淘汰、无源端丢弃，链路丢包单独统计。
