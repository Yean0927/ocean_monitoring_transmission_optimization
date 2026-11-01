# 动态海缆链路配置包

本包提供与项目协议评估一致的 60 min 时变海缆链路配置，供本地 NS-3 或其他网络实验复现。

## 文件

| 文件 | 用途 |
| --- | --- |
| `dynamic-link-fluctuation.csv` | 唯一实验状态输入；固定种子 31、30 s 粒度的 121 个采样点 |
| `plot-dynamic-link-fluctuation.py` | 用于重新生成 CSV 和 SVG 链路图的脚本 |
| `README.md` | 本说明 |

## 状态定义

- 总时长：60 min
- 有效执行片段：120 个，每段 30 s
- 使用规则：第 `i` 行（仅 `time_min < 60`）定义 `[time_min, time_min + 0.5 min)` 的状态。
- `time_min=60.0` 是绘图终点，**不执行额外片段**。
- `capacity_mbps` 在全部片段中固定为 2 Mbps；时变项是 `rtt_ms` 和 `packet_loss_rate`。

| CSV 字段 | NS-3 含义 |
| --- | --- |
| `capacity_mbps` | 瓶颈带宽：`--bottleneckRate=<value>Mbps` |
| `rtt_ms` | 端到端 RTT；设置单向时延为 `--bottleneckDelay=(rtt_ms/2)ms` |
| `packet_loss_rate` | 每包独立丢失概率，取值为 0–1；如 0.1217 表示 12.17% |
| `phase`、`severity` | 分段统计与自适应算法特征，不直接作为协议栈属性 |

## 单片段接入示例

假设 NS-3 根目录为当前目录，第一段（0–30 s）的配置为：

```bash
./build/scratch/ns3-dev-tcp-exp-default \
  --tcpType=ns3::TcpBbr \
  --accessDelay=0ms --egressDelay=0ms \
  --bottleneckRate=2Mbps \
  --bottleneckDelay=39.401ms \
  --bottleneckLoss=0.002744 \
  --stopTime=30
```

其中 `39.401 ms = 78.802 ms / 2`。逐片段模式下，请将每行的 `time_min`、`phase`、RTT、丢包率和随机种子写入结果，便于按时间合并。

## 连续实验注意事项

要保持 TCP/QUIC 拥塞窗口、重传和缓存状态连续，需在同一次 3600 s 仿真中每 30 s 更新带宽、正反向丢包模型；RTT 的热更新需要使用支持运行时修改传播时延的自定义 Channel/DelayModel。不能只读取 CSV 而继续使用启动时的静态链路参数。

## 再生成

```bash
python3 plot-dynamic-link-fluctuation.py --seed 31 --step-min 0.5 \
  --output dynamic-link-fluctuation.svg \
  --csv-output dynamic-link-fluctuation.csv
```

预期校验：CSV 共 122 行（1 行表头 + 121 个采样点）。
