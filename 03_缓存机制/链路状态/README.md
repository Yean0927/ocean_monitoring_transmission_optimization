# 共用链路状态

缓存容量实验和正式不同优先级实验都需要本目录 CSV，无需各保存一份配置。

- `dynamic-link-fluctuation.csv`：固定种子 31、0–60 min、30 s 粒度，共 121 个状态点；末尾 time_min=60 为终点，不构成额外运行片段。
- `code/link_profile.py`：生成相同链路输入参数的代码，来自 ocean/shared/link_profile.py，不生成论文图表。
- `images/dynamic-link-bandwidth-over-time.svg`：原有链路图，包含原带宽和按丢包率折算的有效带宽。

CSV 列为 time_min、phase、capacity_mbps、rtt_ms、packet_loss_rate、severity。全部物理带宽值固定为 2 Mbps，状态变化来自 RTT 和丢包率；不能将状态名称解释为实际带宽升降。

![原链路图](images/dynamic-link-bandwidth-over-time.svg)

如需重建输入，在 ocean 根目录执行（写到运行目录，不覆盖原配置）：

```sh
python 03_缓存机制/链路状态/code/link_profile.py --csv-output runs/link-profile/dynamic-link-fluctuation.csv
```

正式包级报告以 23.5 min、42 min、60 min 为统计检查点。早期离散报告以 24/42 min 作趋势说明，两者不强行合并。早期 P1–P5 离散仿真使用代码内定义场景，不直接读取本 CSV。
