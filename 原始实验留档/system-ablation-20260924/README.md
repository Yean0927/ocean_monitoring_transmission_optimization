# 首轮系统消融（2026-09-24）

结果入口：[results/report.md](results/report.md)。这是先用现有资料跑通的一轮单种子探索实验；调整参数后应另建输出目录，保留本轮结果。

## 五组定义

| 组别 | 协议 | 压缩 | N1 等待队列 |
|---|---|---|---|
| FULL | 交接包 XGBoost | 实际编码产物 | 50 MB Priority-MaxF |
| WO_PROTOCOL | TCP CUBIC | 同 FULL | 同 FULL |
| WO_COMPRESSION | 同一 XGBoost，输入未压缩特征 | 不执行新增压缩 | 同 FULL |
| WO_CACHE | 同 FULL | 同 FULL | 无等待队列，忙时丢弃 |
| BASELINE | TCP CUBIC | 不执行新增压缩 | 无等待队列 |

N0—N1—N2—N3，N1—N2 为 2 Mbps 动态延迟、丢包链路。N0 模拟传感器侧逐记录或媒体分段发送，N1 作为首个路由/缓存节点收齐文件后组装并压缩。使用真实 ns-3 协议栈和实际文件字节；每份独特内容在准备阶段真实编码、解码并校验，仿真回放该内容实测的编解码耗时，不使用报告中的压缩比例。

组装区、在服务文件和传输协议缓冲对所有组保留，均不计入 50 MB 等待队列。NoCache 关闭的是应用等待队列。CPU 不设并行任务上限。本轮缓存项为完整文件，服务不抢占，和第三阶段 packet 缓存的粒度不同。

## 初始参数与调整入口

`prepare.py --help` 可查看参数：

- `--duration 3600 --drain 300 --cache-bytes 50000000`
- `--text-periods 12,12,0.02,120`：D1～D4 记录间隔，秒。
- `--text-waits 120,300,1,1800`：D1～D4 最大组装等待，秒；原文件大小为上限。
- `--image-period 1 --image-quality 75`：九图中位数对应的实际 PNG，JPEG 候选参数。
- `--video-bytes-per-second 195875`：真实片段顺序循环，收齐一段再编码。
- `--output`：新的准备目录；`--ffmpeg`：可用 FFmpeg 的绝对路径。

文本最长等待是本轮暂定值，不是第三阶段的既定参数。JPEG-Q75 也只是候选配置，尚未证明为 2 Mbps 最优。文本/视频编码选择及保真范围详见结果报告。

## 复现流程

保留此目录在原工作区中，准备脚本会引用第二阶段压缩代码、图像编码实现、原始数据和用户的 `xgboost-ablation-handoff`。

1. 使用 Python 3.12 环境安装 `requirements.txt`，准备支持 libx264/libx265 的 FFmpeg。macOS XGBoost 还需 libomp。先运行交接包的 `run.py verify` 验证模型；不需要训练。
2. 准备真实编码产物及模型预测：

```sh
python prepare.py --output prepared --ffmpeg /absolute/path/to/ffmpeg
```

3. 在 ns-3.42 中安装 SIGNET QUIC，固定提交 `833aea6e82fa16bddd6586461ebbcf44f0db0d69`（来源见 `provenance.json`）。在模块目录应用 `quic-ns3.42.patch`。补丁包含版本适配、接收重组、ACK/重传、流量控制和帧边界修复。接收端还会在流数据出现缺口时，通过同一链路发送缺失字节偏移请求，发送端从历史载荷中重发；这是**非标准 QUIC 扩展**，控制包及重传流量均经过实际瓶颈链路。BBR 拥塞控制算法未改动，但可靠传输行为已改变，本轮性能不能直接视为原一阶段协议栈或标准 QUIC 的性能。该模块并非 ns-3.42 官方内置 QUIC。
4. 将 `system-ablation.cc` 复制到 ns-3 的 `scratch/`，重新配置并构建 `scratch_system-ablation` 目标。`run_experiment.py` 的 `NS3`/`BINARY` 定位当前工作区已有 ns-3.42，迁移时更新路径。
5. 在本目录运行：

```sh
python run_experiment.py --prepared prepared --output results --workers 2
```

只重建报表：

```sh
python run_experiment.py --prepared prepared --output results --summarize-only
```

`--variants` 可指定补跑组；汇总时需五组结果齐全。改变输入参数后，必须五组使用同一份新 prepared 数据，不能混用不同参数结果。

## 校验与统计口径

- 交接模型原生 JSON 与 pipeline 预测一致，历史指标校验通过。
- 编码后按各算法数据保真范围校验；传输前 N1 原始字节校验，N3 编码载荷逐字节校验。
- 总生成字节 = 完整交付的原始等价字节 + 永久丢失字节 + 待完成字节。
- 只把无队列拒收/缓存淘汰记作永久丢失；仿真结束仍在组装或传输的数据单列。
- 主报告的时间指标是按实际生成原始字节加权的全样本受限送达时间：从所属文件首字节生成到 N3 解码完成；未送达字节按 3900 s 观察终点赋予惩罚值。该惩罚值并非文件一直在传输或实际完成时间。仅成功文件的耗时保留在 CSV 的 `success_only_*` 诊断列。
- Parquet/Chimp 沿用第二阶段语义预处理，并不字节级恢复原始日志；图像/视频为有损编码。此次消融尚未分离预处理贡献与编码贡献，也没有质量控制实验。
- 单种子结果不代表统计显著性；相同随机种子共享状态序列，但不同协议发包次数不同，实际随机丢包实现不逐包配对。

`validation/` 是开发校验与故障记录，不是最终五组实验数据。最终完整输出只见 `results/`。
