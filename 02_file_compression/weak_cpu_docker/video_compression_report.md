# Docker 弱 CPU 视频压缩实验报告

> 来源：2026-10-26 用户提供的最新版《video_compression.md》中的 Docker 弱 CPU 视频章节，原文参数和结果原样摘录。完整报告见[视频压缩实验报告](../video_compression/experiment_report.md)。本节原稿没有引用图片，无需另配图片。

## Docker 弱 CPU 视频压缩复现实验结果

更新时间：2026-07-31 19:42:13

本节记录最终 Docker 视频压缩复现实验结果。正式统计口径为 `S0/S1/S2`，不纳入 `S3/AV1`；传输分片大小固定为 `4096 bytes`，不建模协议包头开销。重复次数按方案设置：`S0=10`、`S1=10`、`S2=5`。本节端到端结果采用 `T_video = T_encode + T_transfer + T_decode`，解码校验耗时计入压缩方案的总时延，同时保留解码实时倍率用于独立播放适用性分析。

本轮正式完成 `Host-Docker` 与 `Edge-XL / Raspberry Pi 5` 两个 profile；`Edge-4C-L` 与 `Edge-8C-P` 曾产生少量 S0 临时行，但已停止且不纳入正式结果。

### Profile 完成状态

| Profile | 状态 | CPU 限制 | 内存限制 | measurement 行数 | 方案覆盖 | 完整性 |
|---|---|---|---|---:|---|---|
| Host-Docker | completed | unlimited | unlimited | 225 | S0:90, S1:90, S2:45 | pass:225 |
| Edge-XL / Raspberry Pi 5 | completed | 100000/160000（1.60 vCPU；4 核可见） | 4GB | 225 | S0:90, S1:90, S2:45 | pass:225 |
| Edge-4C-L | 不纳入正式结果 | 100000/320000（3.20 vCPU；4 核可见） | 4GB | 临时 S0:10 | 未完整 | 排除 |
| Edge-8C-P | 不纳入正式结果 | 100000/320000（3.20 vCPU；8 核可见） | 4GB | 临时 S0:10 | 未完整 | 排除 |

### 方案级平均结果

| Profile | Scheme | 视频数 | 重复数 | 平均压缩比 | 平均编码时间(s) | 平均解码校验时间(s) | 平均编码吞吐(MB/s) | 平均解码校验吞吐(MB/s) | 正收益场景/总场景 | 平均时延缩短率（计入解码） |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Host-Docker | S0 原始直传 | 9 | 10 | 1.000 | 0.00 | 0.42 | - | 23.22 | 0/27 | 0.0% |
| Host-Docker | S1 H.264降码率 | 9 | 10 | 0.336 | 23.38 | 4.09 | 5.19 | 21.28 | 23/27 | 35.4% |
| Host-Docker | S2 H.265/HEVC | 9 | 5 | 0.189 | 41.84 | 5.01 | 2.54 | 14.97 | 22/27 | 25.3% |
| Edge-XL / Raspberry Pi 5 | S0 原始直传 | 9 | 10 | 1.000 | 0.00 | 1.46 | - | 11.68 | 0/27 | 0.0% |
| Edge-XL / Raspberry Pi 5 | S1 H.264降码率 | 9 | 10 | 0.335 | 87.19 | 11.10 | 1.94 | 15.69 | 17/27 | -42.7% |
| Edge-XL / Raspberry Pi 5 | S2 H.265/HEVC | 9 | 5 | 0.189 | 253.17 | 12.94 | 1.01 | 13.25 | 15/27 | -182.8% |

### 解码校验与播放适用性

| Profile | Scheme | 平均解码实时倍率 | 最小解码实时倍率 | 适用性判断 |
|---|---|---:|---:|---|
| Host-Docker | S0 原始直传 | 92.32x | 43.88x | 整体快于实时播放 |
| Host-Docker | S1 H.264降码率 | 108.30x | 2.21x | 整体快于实时播放 |
| Host-Docker | S2 H.265/HEVC | 76.24x | 1.83x | 整体快于实时播放 |
| Edge-XL / Raspberry Pi 5 | S0 原始直传 | 54.93x | 9.14x | 整体快于实时播放 |
| Edge-XL / Raspberry Pi 5 | S1 H.264降码率 | 80.70x | 0.81x | 存在低于实时播放风险 |
| Edge-XL / Raspberry Pi 5 | S2 H.265/HEVC | 68.37x | 0.70x | 存在低于实时播放风险 |

### 不同带宽下最优方案次数

| Profile | 带宽 | S0 最优次数 | S1 最优次数 | S2 最优次数 |
|---|---:|---:|---:|---:|
| Host-Docker | 2 Mbps | 0 | 2 | 7 |
| Host-Docker | 4 Mbps | 1 | 6 | 2 |
| Host-Docker | 10 Mbps | 3 | 6 | 0 |
| Edge-XL / Raspberry Pi 5 | 2 Mbps | 3 | 6 | 0 |
| Edge-XL / Raspberry Pi 5 | 4 Mbps | 3 | 6 | 0 |
| Edge-XL / Raspberry Pi 5 | 10 Mbps | 4 | 5 | 0 |

### 按视频和带宽的推荐方案

推荐方案按每个 `视频 × 带宽` 下端到端传输时延 `T_video = T_encode + T_transfer + T_decode` 最小确定；S0 仍使用直接传输基线。

### Host-Docker 按视频/带宽推荐

| 视频文件 | 2 Mbps | 4 Mbps | 10 Mbps |
|---|---|---|---|
| 2019-05-30_18.50.28.mkv | S1 | S0 | S0 |
| 3f2b041a2f5cf63ddc2e449fa7e3fd80.mp4 | S2 | S2 | S0 |
| 4412e5bfafeaa07161d2082422e349e1.mp4 | S1 | S1 | S1 |
| 48290d122823a5cf9af2a146ba3d238b.mp4 | S2 | S1 | S1 |
| 4a3b00dd39998a85cb1db439bf0bbe93.mp4 | S2 | S1 | S1 |
| 5cf7af68d381d7cb80e5567444e894c2.mp4 | S2 | S1 | S1 |
| 5fdbdd4dd7b628c0986de9028e8be48a.mp4 | S2 | S2 | S0 |
| 705ccbb00cfbaab61780706633e3c7ce.mp4 | S2 | S1 | S1 |
| ba5cd3bd2090f260c1810d600604f038.mp4 | S2 | S1 | S1 |

### Edge-XL / Raspberry Pi 5 按视频/带宽推荐

| 视频文件 | 2 Mbps | 4 Mbps | 10 Mbps |
|---|---|---|---|
| 2019-05-30_18.50.28.mkv | S0 | S0 | S0 |
| 3f2b041a2f5cf63ddc2e449fa7e3fd80.mp4 | S0 | S0 | S0 |
| 4412e5bfafeaa07161d2082422e349e1.mp4 | S1 | S1 | S1 |
| 48290d122823a5cf9af2a146ba3d238b.mp4 | S1 | S1 | S1 |
| 4a3b00dd39998a85cb1db439bf0bbe93.mp4 | S1 | S1 | S1 |
| 5cf7af68d381d7cb80e5567444e894c2.mp4 | S1 | S1 | S1 |
| 5fdbdd4dd7b628c0986de9028e8be48a.mp4 | S0 | S0 | S0 |
| 705ccbb00cfbaab61780706633e3c7ce.mp4 | S1 | S1 | S1 |
| ba5cd3bd2090f260c1810d600604f038.mp4 | S1 | S1 | S0 |

### 结果解释口径

- `S0` 是原始视频直传基线，不产生编码开销，但传输体积最大。
- `S1` 是 H.264 降码率重编码，Host-Docker 与 Edge-XL 下均是最稳健的实时/准实时方案；Edge-XL 中 S1 在 17/27 个场景有正收益，但平均端到端传输收益仍为负。
- `S2` 是 H.265/HEVC 转码，平均压缩比最低，Host-Docker 下在低带宽和部分中带宽场景有优势；但在 Edge-XL 的 1.60 vCPU 限制下编码时间显著放大，平均端到端传输收益为负，不适合作为该 profile 的实时主方案。
- 解码校验已计入 S1/S2 的端到端传输时延；Edge-XL 下 S1/S2 的最小解码实时倍率低于 1，说明接收端弱 CPU 播放适用性仍需作为独立约束。
- Edge-XL 的内存占用远低于 4GB，瓶颈主要是 CPU quota 与 H.265 编码耗时，而不是内存。
- 本节不使用 Edge-4C-L / Edge-8C-P 的临时 S0 行得出结论；若后续确定新参数，应清空或隔离这两个目录后重新运行。
