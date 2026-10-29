"""Build the Chinese case study from completed resource sensitivity trials."""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE/'resource-experiment'
summary = json.loads((EXP/'summary.json').read_text())
trials = json.loads((EXP/'trials.json').read_text())
calibration = json.loads((EXP/'cpu-calibration.json').read_text())
assert len(summary) == 27 and len(trials) == 135
assert all(r['n'] == 5 for r in summary)
assert all(r['status'] == 'delivered' and r['protocol'] == 'TCP_CUBIC' for r in trials)
names = {'D2':'Text (D2)', 'V1':'Video (V1)', 'I1':'Image (I1)'}
def point(stream, resource, quality):
    return next(r for r in summary if (r['stream'],r['resource'],r['quality'])==(stream,resource,quality))
def shift(stream, resource):
    p,g = [point(stream,resource,q)['mean_jct_s'] for q in ['Poor','Good']]
    return p,g,100*(p-g)/p
def discussion(stream):
    return '；'.join(f"{label}改善时，平均 JCT 从 {p:.4f} s 降至 {g:.4f} s，"+
                    (f"降低 {percent:.2f}%" if percent >= .01 else "降幅不足 0.01%")
                    for resource,label in [('Delay','RTT'),('BW','带宽'),('CPU','CPU 条件')]
                    for p,g,percent in [shift(stream,resource)])+'。'
table1 = '\n'.join(f"| {'Bandwidth' if r['resource']=='BW' else r['resource']} | {r['quality']} | "
                   f"{r['rtt_ms']:.2f} ms | {r['bandwidth_mbps']} Mbps | "
                   f"{ {'cpu1':'1 vCPU','cpu4':'4 vCPU','shared1':'1 shared vCPU'}[r['cpu_profile']]} |"
                   for r in summary if r['stream']=='D2')
baseline = {s:point(s,'BW','Poor') for s in names}
table2 = '\n'.join(f"| {names[s]} | {next(r['raw_bytes'] for r in trials if r['stream']==s):,} | "
                   f"{b['mean_compressed_bytes']:,.0f} | {b['mean_compression_s']*1000:.3f} | "
                   f"{b['mean_transport_s']*1000:.3f} | {b['mean_decompression_s']*1000:.3f} | "
                   f"{b['mean_jct_s']:.4f} |"
                   for s,b in baseline.items())
table3 = '\n'.join(f"| {names[s]} | {resource} | "+' | '.join(
                    f"{point(s,resource,q)['mean_jct_s']:.6f} ± {point(s,resource,q)['sd_jct_s']:.6f}"
                    for q in ['Poor','Medium','Good'])+' |'
                    for s in names for resource in ['Delay','BW','CPU'])
cpu_compression = [point('V1','CPU',q)['mean_compression_s'] for q in ['Poor','Medium','Good']]
cpu_decompression = [point('V1','CPU',q)['mean_decompression_s'] for q in ['Poor','Medium','Good']]
processing_shares = {s:100*(b['mean_compression_s']+b['mean_decompression_s'])/b['mean_jct_s']
                     for s,b in baseline.items()}
text_share = f"{processing_shares['D2']:.2f}%" if processing_shares['D2'] >= .01 else '不足 0.01%'
main = rf'''# II. 研究动机案例分析

海洋监测平台同时传输文本观测、视频和图像。三类对象的文件规模与压缩处理开销不同，同一资源调整因而可能带来不同的完成时间变化。本节通过受控资源对照，考察链路时延、带宽与 CPU 对文件传输的影响，为后续联合优化提供依据。

## A. 数据对象与完成时间

我们选取普通气象文本（D2）、海洋视频（V1）和海洋图像（I1）作为代表对象。D2 包含 11 条观测及 1 行表头，原始大小为 1098 B，采用 Gzip level 6；V1 为 4354778 B 的视频文件，采用 H.265/HEVC（S2，fast preset，CRF 30）；I1 为九张图像中按原始大小排序的中位项，大小为 258715 B，采用 JPEG Q75。三类对象均在首个缓存节点 N1 完成组装后压缩，沿 N1–N2–N3 路径传输。

为分离资源影响与传感器聚合等待，本案例从 N1 完整组装并校验原始文件的时刻 $a_i^{{N1}}$ 开始计时，以 N3 完成接收校验并完成解压缩的时刻 $d_i$ 为终点。文件完成时间（JCT）定义为：

$$
T_{{\mathrm{{JCT}},i}}=d_i-a_i^{{N1}}
=T_{{\mathrm{{compress}},i}}+T_{{\mathrm{{queue}},i}}
+T_{{\mathrm{{transfer}},i}}+T_{{\mathrm{{decompress}},i}}.
$$

此处 $T_{{\mathrm{{transfer}}}}$ 使用网络仿真的发送和接收时间戳，包含连接建立、协议处理和传输等待。每次仿真只有一个文件对象，发送队列无竞争。该 JCT 不包含源端记录累积至 N1 完整组装的时间；系统消融中的首字节生成至完整送达时间仍包含这一过程，两项指标分别用于资源敏感性与整体系统评价。

## B. 资源配置与测量方法

我们分别改变链路时延、带宽和 CPU 条件，其余资源保持表 I 中的固定配置。RTT 档位取已有动态链路轨迹的第 90、50 和 10 百分位数，带宽设置为 2、4 和 10 Mbps。资源对照使用固定链路条件，以便识别单项资源的影响；已有系统消融继续使用逐状态的动态链路输入。

**TABLE I. RESOURCE CONFIGURATIONS IN THE CASE STUDY**

| Service Resource | Service Quality | Delay (RTT) | Bandwidth | CPU |
|---|---|---:|---:|---|
{table1}

CPU 通过进程及其子进程的累计 CPU 时间额度控制：1 vCPU 与 4 vCPU 分别设置为 1 和 4 CPU-s/s，视频压缩线程池分别设为 1 和 4。1 shared vCPU 采用 0.5 CPU-s/s 模拟单个 vCPU 的 50% 可用时间份额。该设置是软件时间配额的近似控制，不是物理核心绑定或真实多租户竞争；短时标定的实际 CPU-s/s 分别为 {calibration['cpu1']['cpu_per_wall']:.3f}、{calibration['cpu4']['cpu_per_wall']:.3f} 和 {calibration['shared1']['cpu_per_wall']:.3f}。单线程 Gzip 与 JPEG 不会因额度增至 4 vCPU 而自动获得四倍并行能力。

压缩和解压缩均实际执行并保存输出文件。D2 通过解压缩后的逐字节一致性校验；图像通过完整解压缩与尺寸检查；视频通过全帧解压缩检查。图像和视频采用有损压缩，本案例未测量 PSNR、SSIM 或 VMAF，结果限于这些固定方案的处理与传输开销。

网络部分复用四节点 ns-3 程序，入口和出口链路为 100 Mbps，N1–N2 为表 I 的瓶颈链路，单向传播时延为 RTT/2。为排除协议切换的影响，各配置均使用 TCP CUBIC，外加随机丢包率设为 0；实际压缩字节通过协议栈传输，并在 N3 与保存的压缩文件逐字节比对。实测压缩、解压缩耗时作为对应处理事件的持续时间输入仿真。

每个 CPU 条件下的每类对象进行 5 次处理测量，同一次处理测量在 Delay、BW 及 CPU-Medium 配置间配对复用。共得到 45 组压缩与解压缩测量、135 次独立网络仿真，以及 27 个配置均值。所有仿真统一在 3600 s 截止，135 次试验均在截止前完成。结果报告均值与样本标准差；重复次数反映同一对象的技术重复，不代表不同海洋数据样本的分布。

## C. 完成时间对资源的响应

表 II 给出 RTT 为 153.61 ms、带宽为 2 Mbps、CPU 为 1 vCPU 时的处理与传输开销。视频压缩与解压缩占 JCT 的 {processing_shares['V1']:.2f}%，文本占比{text_share}，图像占比为 {processing_shares['I1']:.2f}%，说明三类对象在相同资源条件下具有不同的时间构成。

**TABLE II. MEASURED PROCESSING AND TRANSFER COSTS AT 2 Mbps AND 1 vCPU**

| Data Type | Original Size (B) | Compressed Size (B) | Compression (ms) | Transfer (ms) | Decompression (ms) | Avg. JCT (s) |
|---|---:|---:|---:|---:|---:|---:|
{table2}

Values are means of five technical repetitions. Transfer uses ns-3 event timestamps and includes TCP connection establishment.


**图 2. 三类海洋监测数据的资源敏感性。**（a）气象文本 D2；（b）海洋视频 V1；（c）海洋图像 I1。每个面板横轴为 Poor、Medium、Good，三条曲线分别表示改善时延资源（Delay，黑色菱形实线）、带宽资源（BW，粉色圆点虚线）和 CPU 资源（CPU，蓝色三角点线），具体配置见表 I。点为 5 次技术重复的平均 JCT，误差棒为样本标准差；小于标记尺寸的误差棒可能不可见，重合的曲线表示完成时间相同或接近。纵轴单位均为 s，各面板独立缩放。JCT 从 N1 完整文件可用计至 N3 解压缩完成，包含实测处理时间与 ns-3 协议栈传输时间。

**文本对象。**{discussion('D2')} D2 压缩后的文件为 278 B，体积减少 74.68%。文件体积较小，压缩和解压缩的绝对开销较低，完成时间主要受连接建立及传播等待影响。其文件级资源响应与低速率记录的聚合等待应分别评价，不能据本图推断源端记录会立即送达。

**视频对象。**{discussion('V1')} 在 CPU 的三个档位下，平均压缩时间分别为 {cpu_compression[0]:.3f}、{cpu_compression[1]:.3f} 和 {cpu_compression[2]:.3f} s，平均解压缩时间分别为 {cpu_decompression[0]:.3f}、{cpu_decompression[1]:.3f} 和 {cpu_decompression[2]:.3f} s。计算份额与线程配置明显改变处理耗时，而较大的压缩文件仍需占用链路传输时间。因此，视频压缩方案的评价需要同时考虑处理能力和可用带宽。

**图像对象。**{discussion('I1')} 图像压缩后的文件为 31778 B，体积减少 87.72%。JPEG 处理时间较短，但压缩后的文件仍需经历 TCP 的连接建立和数据传输。其完成时间受传播等待与带宽共同影响，CPU 份额改善的作用较小。

## D. 资源需求与优化动机

上述结果支持依据实际完成时间响应区分资源需求。小批次文本在本工况下表现出明显的时延敏感性；视频对计算份额的变化响应显著，同时受带宽制约；图像的响应主要来自网络侧资源。三种需求并非与数据类型固定绑定：文件大小、聚合策略、压缩方案与资源范围改变后，其主导因素也可能变化。

因此，海洋监测数据的传输优化需要联合评价协议交互、压缩处理和缓存等待。文本应兼顾聚合时限与连接开销，视频应结合计算与带宽条件选择压缩方案，图像应权衡压缩后体积与网络传输开销。本节的单对象对照用于说明资源影响，协议自适应和缓存调度对并发数据流的贡献由系统消融实验评价。
'''
notes = f'''# 补测证据与复现口径

## 已完成的测量

- 3 类对象 × 3 个 CPU 配置 × 5 次技术重复，共 45 组实际压缩、解压缩测量。
- 3 类对象 × 9 个资源配置 × 5 次，共 135 次 ns-3 仿真，全部完整送达。
- 27 个绘图点均有对应试验；没有空值、按平均压缩比替代的文件或大小/带宽替代的网络完成时间。
- 原程序使用 MilliSeconds(rtt/2)，会截断小数毫秒。本案例构建独立程序改为 Seconds(rtt/2000.0)，保留时延精度后重跑 135 次网络试验。初次诊断结果单独归档，不参与最终统计。
- 校验：D2 原始字节无损恢复；图像完整解压缩及 1280×720 尺寸；视频全帧解压缩；N1 原文件及 N3 压缩文件的逐字节检查。

## 可复现文件

- [试验入口]({HERE/'run_resource_experiment.py'})
- [仿真程序构建入口]({HERE/'build_resource_simulator.py'})：首次运行须先构建，再执行试验入口。
- [真实处理测量]({HERE/'codec_worker.py'})
- [配置、版本和 SHA-256]({EXP/'run-config.json'})
- [结果审计]({EXP/'audit.json'})
- [独立仿真程序的构建记录]({EXP/'simulator-build.json'})
- [CPU 标定]({EXP/'cpu-calibration.json'})
- [45 组处理测量]({EXP/'codec-measurements.json'})
- [135 次事件结果]({EXP/'trials.json'})
- [27 个点汇总 CSV]({EXP/'summary.csv'})
- [绘图脚本]({HERE/'plot_case_study.py'})
- [原有大小/B 名义计算及 FULL 代表事件]({HERE/'case_measurements.json'})：保留为历史计算，不参与新图。

每次处理的完整日志、CPU 配额控制记录和实际压缩文件位于 resource-experiment/codec，各次网络试验的输入、事件 trace.csv、协议决策和链路计数位于 resource-experiment/network。结果可由保存的处理耗时与网络事件核对。

## 计量边界

CPU 配额由进程组暂停/恢复实现，目标为 0.5/1/4 CPU-s/s。控制器约每 3 ms 采样，有 3 ms 突发容差；标定的实际速率如下。此方式是软配额近似，非物理核心或 Docker 容器隔离。

| CPU Profile | Target CPU-s/s | Calibration CPU-s/s |
|---|---:|---:|
| 1 shared vCPU | 0.5 | {calibration['shared1']['cpu_per_wall']:.6f} |
| 1 vCPU | 1 | {calibration['cpu1']['cpu_per_wall']:.6f} |
| 4 vCPU | 4 | {calibration['cpu4']['cpu_per_wall']:.6f} |

D2 的压缩和解压缩分别循环 10000 与 40000 次，图像分别循环 50 与 500 次，采用批次总壁钟时间除以循环数，减轻单次计时噪声。初始化和文件保存不在测量区间；内存压缩、内存解压缩和图像像素加载在区间内。视频每次单独运行 FFmpeg，包含进程启动、文件读写和完整视频处理，其计量范围与内存文本/图像处理有差异。

不同线程配置下 H.265 的输出字节数可略有不同，网络仿真使用各次实际输出。跨条件共用同次处理测量用于配对；误差棒为 5 次技术重复的样本标准差，不表示数据类型总体变异。固定无外加随机丢包的 TCP 仿真不代表实海况声学链路测量；当前对照考察已有框架中的链路资源变化。

新 JCT 从 N1 文件组装完成计时，未测传感器采集周期或聚合等待；它与原系统首字节至送达指标不能直接混用。单对象无发送队列竞争，不能由此推断 Priority-MaxF 缓存贡献。图像/视频缺少画质等效指标，不能声称无损或质量相同。

## 全部绘图数据（s，mean ± SD，n=5）

| Data Type | Resource | Poor | Medium | Good |
|---|---|---:|---:|---:|
{table3}

## 证据分配

正文保留资源配置、基准开销、三类对象的资源响应及联合优化动机。每次运行的 CPU 控制和哈希日志保留在原始测量目录，全部 27 个点与重复设计保留于本说明及 source data。沿用用户提供参考案例的资源对照形式，不复用其网站结果，不强行将三类数据与三类资源一一对应。
'''
(HERE/'case_study.md').write_text(main, encoding='utf-8')
(HERE/'evidence_notes.md').write_text(notes, encoding='utf-8')
print('Updated case_study.md and evidence_notes.md from 135 completed trials')
