# 补测证据与复现口径

## 已完成的测量

- 3 类对象 × 3 个 CPU 配置 × 5 次技术重复，共 45 组实际压缩、解压缩测量。
- 3 类对象 × 9 个资源配置 × 5 次，共 135 次 ns-3 仿真，全部完整送达。
- 27 个绘图点均有对应试验；没有空值、按平均压缩比替代的文件或大小/带宽替代的网络完成时间。
- 原程序使用 MilliSeconds(rtt/2)，会截断小数毫秒。本案例构建独立程序改为 Seconds(rtt/2000.0)，保留时延精度后重跑 135 次网络试验。初次诊断结果单独归档，不参与最终统计。
- 校验：D2 原始字节无损恢复；图像完整解压缩及 1280×720 尺寸；视频全帧解压缩；N1 原文件及 N3 压缩文件的逐字节检查。

## 可复现文件

- [试验入口](/Users/yean/program/海洋监测/outputs/marine-data-case-study/run_resource_experiment.py)
- [仿真程序构建入口](/Users/yean/program/海洋监测/outputs/marine-data-case-study/build_resource_simulator.py)：首次运行须先构建，再执行试验入口。
- [真实处理测量](/Users/yean/program/海洋监测/outputs/marine-data-case-study/codec_worker.py)
- [配置、版本和 SHA-256](/Users/yean/program/海洋监测/outputs/marine-data-case-study/resource-experiment/run-config.json)
- [结果审计](/Users/yean/program/海洋监测/outputs/marine-data-case-study/resource-experiment/audit.json)
- [独立仿真程序的构建记录](/Users/yean/program/海洋监测/outputs/marine-data-case-study/resource-experiment/simulator-build.json)
- [CPU 标定](/Users/yean/program/海洋监测/outputs/marine-data-case-study/resource-experiment/cpu-calibration.json)
- [45 组处理测量](/Users/yean/program/海洋监测/outputs/marine-data-case-study/resource-experiment/codec-measurements.json)
- [135 次事件结果](/Users/yean/program/海洋监测/outputs/marine-data-case-study/resource-experiment/trials.json)
- [27 个点汇总 CSV](/Users/yean/program/海洋监测/outputs/marine-data-case-study/resource-experiment/summary.csv)
- [绘图脚本](/Users/yean/program/海洋监测/outputs/marine-data-case-study/plot_case_study.py)
- [原有大小/B 名义计算及 FULL 代表事件](/Users/yean/program/海洋监测/outputs/marine-data-case-study/case_measurements.json)：保留为历史计算，不参与新图。

每次处理的完整日志、CPU 配额控制记录和实际压缩文件位于 resource-experiment/codec，各次网络试验的输入、事件 trace.csv、协议决策和链路计数位于 resource-experiment/network。结果可由保存的处理耗时与网络事件核对。

## 计量边界

CPU 配额由进程组暂停/恢复实现，目标为 0.5/1/4 CPU-s/s。控制器约每 3 ms 采样，有 3 ms 突发容差；标定的实际速率如下。此方式是软配额近似，非物理核心或 Docker 容器隔离。

| CPU Profile | Target CPU-s/s | Calibration CPU-s/s |
|---|---:|---:|
| 1 shared vCPU | 0.5 | 0.570844 |
| 1 vCPU | 1 | 1.011862 |
| 4 vCPU | 4 | 3.953438 |

D2 的压缩和解压缩分别循环 10000 与 40000 次，图像分别循环 50 与 500 次，采用批次总壁钟时间除以循环数，减轻单次计时噪声。初始化和文件保存不在测量区间；内存压缩、内存解压缩和图像像素加载在区间内。视频每次单独运行 FFmpeg，包含进程启动、文件读写和完整视频处理，其计量范围与内存文本/图像处理有差异。

不同线程配置下 H.265 的输出字节数可略有不同，网络仿真使用各次实际输出。跨条件共用同次处理测量用于配对；误差棒为 5 次技术重复的样本标准差，不表示数据类型总体变异。固定无外加随机丢包的 TCP 仿真不代表实海况声学链路测量；当前对照考察已有框架中的链路资源变化。

新 JCT 从 N1 文件组装完成计时，未测传感器采集周期或聚合等待；它与原系统首字节至送达指标不能直接混用。单对象无发送队列竞争，不能由此推断 Priority-MaxF 缓存贡献。图像/视频缺少画质等效指标，不能声称无损或质量相同。

## 全部绘图数据（s，mean ± SD，n=5）

| Data Type | Resource | Poor | Medium | Good |
|---|---|---:|---:|---:|
| Text (D2) | Delay | 0.293656 ± 0.000000 | 0.232501 ± 0.000000 | 0.129646 ± 0.000000 |
| Text (D2) | BW | 0.232501 ± 0.000000 | 0.231481 ± 0.000000 | 0.230869 ± 0.000000 |
| Text (D2) | CPU | 0.232512 ± 0.000001 | 0.232501 ± 0.000000 | 0.232501 ± 0.000000 |
| Video (V1) | Delay | 13.248956 ± 0.023402 | 13.106261 ± 0.023402 | 12.883022 ± 0.023402 |
| Video (V1) | BW | 13.106261 ± 0.023402 | 10.715414 ± 0.022488 | 9.714913 ± 0.021949 |
| Video (V1) | CPU | 23.698996 ± 0.077717 | 13.106261 ± 0.023402 | 8.845562 ± 0.008500 |
| Image (I1) | Delay | 0.569518 ± 0.000050 | 0.467593 ± 0.000050 | 0.296168 ± 0.000050 |
| Image (I1) | BW | 0.467593 ± 0.000050 | 0.428233 ± 0.000050 | 0.404617 ± 0.000050 |
| Image (I1) | CPU | 0.473110 ± 0.000129 | 0.467593 ± 0.000050 | 0.467717 ± 0.000224 |

## 证据分配

正文保留资源配置、基准开销、三类对象的资源响应及联合优化动机。每次运行的 CPU 控制和哈希日志保留在原始测量目录，全部 27 个点与重复设计保留于本说明及 source data。沿用用户提供参考案例的资源对照形式，不复用其网站结果，不强行将三类数据与三类资源一一对应。
