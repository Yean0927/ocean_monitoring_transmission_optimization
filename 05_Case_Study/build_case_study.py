"""Build a source-grounded case study from saved measurements; no experiment rerun."""

# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT / 'data/images'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT / 'raw_experiments/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

import csv
import hashlib
import json
import shutil
import runpy
from pathlib import Path

OUT = Path(__file__).resolve().parent
if (OUT / 'resource-experiment/summary.json').exists():
    runpy.run_path(str(OUT/'build_measured_case_study.py'), run_name='__main__')
    raise SystemExit(0)
ROOT = OCEAN_ROOT
EXP = ROOT / '04_ablation_experiments/system_20260928'
measurements = json.loads((EXP / 'prepared/codec-measurements.json').read_text())
files = json.loads((EXP / 'prepared/files.json').read_text())
with (EXP / 'results/FULL.csv').open() as f:
    events = list(csv.DictReader(f))

# Select by size rather than compression outcome. D2 logical_rows includes its header.
texts = sorted((m for m in measurements if m['stream'] == 'D2' and m['logical_rows'] == 12),
               key=lambda m: (m['raw_bytes'], m['source_sha256']))
images = sorted((p for p in (OCEAN_IMAGE_DIR).iterdir()
                 if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}),
                key=lambda p: (p.stat().st_size, p.name))
assert len(images) == 9
median_image = images[len(images) // 2]
samples = [texts[len(texts) // 2],
           next(m for m in measurements if m['stream'] == 'V1' and
                Path(m['source']).name == 'ba5cd3bd2090f260c1810d600604f038.mp4'),
           next(m for m in measurements if m['stream'] == 'I1' and
                Path(m['source']) == median_image)]
names = {'D2': 'Text (D2)', 'V1': 'Video (V1)', 'I1': 'Image (I1)'}
rows, stages = [], []
for m in samples:
    matched = [f for f in files if m['source_sha256'] in f['raw_path']]
    assert matched
    artifact = matched[0]
    for key, expected in [('raw_path', m['source_sha256']), ('encoded_path', m['encoded_sha256'])]:
        data = Path(artifact[key]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
        assert len(data) == m['raw_bytes' if key == 'raw_path' else 'encoded_bytes']
    delivered = [e for e in events if int(e['id']) in {f['id'] for f in matched}
                 and e['status'] == 'delivered']
    e = min(delivered, key=lambda e: float(e['first_s']))
    fields = ['first_s', 'assembled_s', 'ready_s', 'tx_start_s', 'received_s', 'decoded_s']
    times = [float(e[k]) for k in fields]
    stage = dict(stream=m['stream'], file_id=int(e['id']), times=dict(zip(fields, times)),
                 assembly_s=times[1]-times[0], encode_s=times[2]-times[1],
                 queue_s=times[3]-times[2], network_s=times[4]-times[3],
                 decode_s=times[5]-times[4], total_s=times[5]-times[0])
    assert abs(sum(stage[k] for k in ['assembly_s','encode_s','queue_s','network_s','decode_s'])
               - stage['total_s']) < 1e-9
    stages.append(stage)
    for bandwidth in [2, 4, 10]:
        direct = 8*m['raw_bytes']/(bandwidth*1e6)
        transfer = 8*m['encoded_bytes']/(bandwidth*1e6)
        codec = m['encode_seconds']+m['decode_seconds']
        total = codec+transfer
        rows.append(dict(stream=m['stream'], bandwidth_mbps=bandwidth,
                         direct_s=direct, transfer_s=transfer, codec_s=codec, total_s=total,
                         reduction_pct=100*(direct-total)/direct,
                         codec_share_pct=100*codec/total,
                         direct_with_raw_decode_s=direct+m['raw_decode_seconds']))

with (EXP / 'prepared/link.csv').open() as f:
    link = [r for r in csv.DictReader(f) if float(r['time_min']) < 60]
def quantile(values, p):
    values = sorted(values)
    x = (len(values)-1)*p
    lo = int(x)
    hi = min(lo+1, len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(x-lo)
rtt = [float(r['rtt_ms']) for r in link]
q10, q50, q90 = [quantile(rtt, p) for p in [.1, .5, .9]]

def fmt(x):
    return f'{x:.6f}'

payload_table = '\n'.join(
    f"| {names[m['stream']]} | {m['raw_bytes']:,} | {m['encoded_bytes']:,} | "
    f"{100*(1-m['encoded_bytes']/m['raw_bytes']):.2f}% | "
    f"{m['encode_seconds']*1000:.6f} | {m['decode_seconds']*1000:.6f} |"
    for m in samples)
timing_table = '\n'.join(
    f"| {names[r['stream']]} | {r['bandwidth_mbps']} | {fmt(r['direct_s'])} | "
    f"{fmt(r['transfer_s'])} | {fmt(r['total_s'])} | {r['reduction_pct']:.2f}% | "
    f"{r['codec_share_pct']:.2f}% |" for r in rows)
stage_table = '\n'.join(
    f"| {names[s['stream']]}（ID {s['file_id']}） | {s['assembly_s']:.6f} | "
    f"{s['encode_s']:.6f} | {s['queue_s']:.6f} | {s['network_s']:.6f} | "
    f"{s['decode_s']:.6f} | {s['total_s']:.6f} |" for s in stages)

original_table = '''| 服务资源 | 服务质量 | 时延 | 带宽 | CPU |
|---|---|---:|---:|---|
| Delay | Poor | 131 ms | 248 Mbps | 1 vCPU |
| Delay | Medium | 112 ms | 248 Mbps | 1 vCPU |
| Delay | Good | 96 ms | 248 Mbps | 1 vCPU |
| Bandwidth | Poor | 34 ms | 3 Mbps | 1 vCPU |
| Bandwidth | Medium | 34 ms | 248 Mbps | 1 vCPU |
| Bandwidth | Good | 34 ms | 758 Mbps | 1 vCPU |
| CPU | Poor | 27 ms | 917 Mbps | 1 shared vCPU |
| CPU | Medium | 27 ms | 917 Mbps | 1 vCPU |
| CPU | Good | 27 ms | 917 Mbps | 4 vCPU |'''

codec_stats_table = '\n'.join(
    f"| {names[m['stream']]} | {m['raw_bytes']:,} | {m['encoded_bytes']:,} | "
    f"{m['encode_seconds']*1000:.3f} | {m['decode_seconds']*1000:.3f} | "
    f"{r['transfer_s']*1000:.3f} | {r['codec_share_pct']:.2f} |"
    for m in samples for r in rows if r['stream'] == m['stream'] and r['bandwidth_mbps'] == 2)

main = rf'''# II. 研究动机案例分析

海洋监测平台的数据传输涉及文本观测、视频和图像等不同类型的数据。文件规模、数据产生速率以及压缩与解压缩开销的差异，使不同数据对象在同一链路条件下具有不同的完成时间构成。本节选取三类本地数据开展案例分析，通过分解等待、传输和解压缩时间，说明联合考虑网络与计算资源的必要性。

## A. 三类数据的传输模式

我们选择普通气象文本（D2）、海洋视频（V1）和海洋图像（I1）作为分析对象，分别代表连续记录、视频文件和图像文件三种输入形式。文本对象由 11 条气象观测及 1 行表头组成，原始大小为 1098 B；视频对象的原始大小为 4354778 B；图像对象取九张样本按原始大小排序后的中位项，大小为 258715 B。三类对象均在首个缓存节点 N1 完成组装后压缩，再向接收节点 N3 传输。文本采用 Gzip level 6，视频采用 H.265/HEVC（S2，fast preset，CRF 30），图像采用 JPEG Q75。

为描述实际送达过程，我们将成功文件的完成时间分为等待时间、网络传输时间和解压缩时间。等待时间 $T_{{\mathrm{{wait}}}}$ 定义为源端首字节生成至 N1 开始发送压缩文件的时间，包括数据生成与组装、压缩以及发送队列等待；网络传输时间 $T_{{\mathrm{{net}}}}$ 定义为开始发送至 N3 完成接收与完整性校验的时间；解压缩时间 $T_{{\mathrm{{decompress}}}}$ 为接收完成至解压缩完成的时间。因此，文件的端到端完成时间为：

$$
T_{{\mathrm{{e2e}}}}
=T_{{\mathrm{{wait}}}}+T_{{\mathrm{{net}}}}+T_{{\mathrm{{decompress}}}}
=T_{{\mathrm{{assembly}}}}+T_{{\mathrm{{compress}}}}+T_{{\mathrm{{queue}}}}
+T_{{\mathrm{{net}}}}+T_{{\mathrm{{decompress}}}}.
$$

各阶段占比用于识别完成时间的主要来源。较大的等待时间占比可能源于聚合、压缩或排队，需要结合分项记录判断；较大的网络传输时间占比则提示传输路径对完成时间的贡献较大，仍需通过控制资源条件验证其带宽或时延敏感性。

## B. 资源配置与评价方法

我们将资源敏感性定义为其他条件保持一致时，文件完成时间随资源条件变化的程度，并从链路时延、带宽和 CPU 三个维度设置对照配置，如表 I 所示。时延档位取现有链路轨迹 RTT 的第 90、50 和 10 百分位数，带宽设置为 2、4 和 10 Mbps，CPU 设置为 1 个共享 vCPU、1 vCPU 和 4 vCPU。每组仅改变所考察的资源，三类数据使用相同配置。

**TABLE I. RESOURCE CONFIGURATIONS IN THE CASE STUDY**

| Service Resource | Service Quality | Delay (RTT) | Bandwidth | CPU |
|---|---|---:|---:|---|
| Delay | Poor | {q90:.2f} ms | 2 Mbps | 1 vCPU |
| Delay | Medium | {q50:.2f} ms | 2 Mbps | 1 vCPU |
| Delay | Good | {q10:.2f} ms | 2 Mbps | 1 vCPU |
| Bandwidth | Poor | {q50:.2f} ms | 2 Mbps | 1 vCPU |
| Bandwidth | Medium | {q50:.2f} ms | 4 Mbps | 1 vCPU |
| Bandwidth | Good | {q50:.2f} ms | 10 Mbps | 1 vCPU |
| CPU | Poor | {q50:.2f} ms | 2 Mbps | 1 shared vCPU |
| CPU | Medium | {q50:.2f} ms | 2 Mbps | 1 vCPU |
| CPU | Good | {q50:.2f} ms | 2 Mbps | 4 vCPU |

表 I 为资源敏感性对照的拟定配置，尚未完成全部测量。共享 vCPU 条件下需固定 CPU 竞争负载。以下初步分析采用已有的未显式限制 CPU 的压缩与解压缩测量与动态链路事件记录；固定 RTT 对照与系统消融所使用的逐状态动态链路分别评价。

为单独考察压缩带来的处理与传输开销，我们实际调用压缩与解压缩算法，测量原始大小 $S_0$、压缩后大小 $S_c$、压缩时间和解压缩时间，并按带宽 $B$（Mbps）计算单链路名义传输时间：

$$
\widehat{{T}}_{{\mathrm{{transfer}}}}=\frac{{8S_c}}{{B\times10^6}},\qquad
\widehat{{T}}_{{\mathrm{{compressed}}}}
=T_{{\mathrm{{compress}}}}+\widehat{{T}}_{{\mathrm{{transfer}}}}+T_{{\mathrm{{decompress}}}}.
$$

以原始文件的名义直传时间 $\widehat{{T}}_{{\mathrm{{direct}}}}=8S_0/(B\times10^6)$ 为基线，定义压缩路径的时延缩短率与压缩与解压缩时间占比：

$$
R_{{\mathrm{{latency}}}}
=\frac{{\widehat{{T}}_{{\mathrm{{direct}}}}-\widehat{{T}}_{{\mathrm{{compressed}}}}}}
{{\widehat{{T}}_{{\mathrm{{direct}}}}}}\times100\%,\qquad
f_{{\mathrm{{comp+decomp}}}}
=\frac{{T_{{\mathrm{{compress}}}}+T_{{\mathrm{{decompress}}}}}}
{{\widehat{{T}}_{{\mathrm{{compressed}}}}}}\times100\%.
$$

该名义计算不包含组装、排队、协议开销和重传，直传基线也不包含原始媒体的解压缩时间；完整端到端评价则使用实际事件时间戳。文本完整性通过解压缩后逐字节一致检查，图像通过解压缩与尺寸检查，视频通过完整解压缩检查。后两类为有损压缩，本案例比较其传输开销，不据此声称视觉质量等效。

## C. 完成时间差异与设计动机

三类对象在 2 Mbps 下的压缩、名义传输与解压缩开销如表 II 所示。图像的压缩与解压缩时间仅占压缩路径的 8.28%，而视频达到 35.03%，表明二者在相同带宽下具有不同的处理开销构成。

**TABLE II. COMPRESSION, TRANSFER, AND DECOMPRESSION COSTS AT 2 Mbps**

| Data Type | Original Size (B) | Compressed Size (B) | Compression Time (ms) | Decompression Time (ms) | Nominal Transfer Time (ms) | Processing Share (%) |
|---|---:|---:|---:|---:|---:|---:|
{codec_stats_table}

Processing time = compression time + decompression time.

图 2 按资源敏感性对照的形式组织：每个数据面板的横轴均为 Poor、Medium 和 Good，三条系列分别对应 Delay、BW 和 CPU。每个系列在改变目标资源时保持其余条件一致，完整对照将为每类对象提供九个完成时间点。


**图 2. 三类海洋监测数据的资源敏感性对照布局及已有带宽计算。**（a）气象文本 D2；（b）海洋视频 V1；（c）海洋图像 I1。黑色菱形实线用于 Delay，粉色圆点虚线用于 BW，蓝色三角点线用于 CPU。横轴三个质量档位分别映射到表 I 各资源的 Poor、Medium 和 Good 配置。当前仅绘制已有带宽 2、4、10 Mbps 下的压缩、名义传输与解压缩时间之和，使用的是不限 CPU 的已有测量，不等同于表 I 的固定 1 vCPU 对照。Delay 和 CPU 的对应数据尚缺，仅保留图例并标注待测，不绘制替代数值。文本面板使用 ms，视频与图像使用 s，纵轴独立；图中数值不包含组装、排队、RTT 和重传，也不是重复测量的平均 JCT。

文本的压缩收益需要结合聚合等待进行评价。D2 压缩后的体积减少 74.68%，压缩、名义传输与解压缩合计约 1.137 ms，相比直传缩短 74.11%，但绝对时间仅减少约 3.255 ms。在现有动态链路仿真中，该批次一次成功送达的生成与组装时间约为 294.44 s，首字节生成至解压缩完成共约 294.51 s。该事件表明，小批次文本可以获得较好的压缩效果，但在低生成速率下，聚合等待可能成为完整送达时间的主要来源，需要同时约束批次规模与最长等待时间。

图像在当前低带宽条件下的压缩路径主要耗时于传输。所选图像压缩后的体积减少 87.72%，在 2 Mbps 下的压缩、名义传输与解压缩合计约为 0.139 s，相比直传缩短 86.61%，其中名义传输占 91.72%。当带宽升至 10 Mbps、保持实测压缩与解压缩时间不变时，压缩与解压缩占比增至 31.09%。这说明带宽提高后，固定处理开销在图像完成时间中的相对作用增强。

视频的压缩收益同时受带宽与计算开销制约。所选视频的压缩与解压缩共耗时约 2.612 s。在 2 Mbps 下，压缩路径的名义完成时间为 7.458 s，较直传缩短 57.18%；当带宽增加至 4 Mbps 时，压缩与解压缩占比提高至 51.88%。在 10 Mbps 下，S2 的名义完成时间约为 3.582 s，比直传的 3.484 s 增加 2.81%。因此，更小的输出文件并不必然对应更短的完成时间，带宽变化后需要重新比较压缩方案与直传。

计算资源也会改变视频方案的选择。在原第二阶段同一视频、同一主机的 CPU 配额实验中，2 Mbps 下的最优方案由 1.6 vCPU 配额时的 S1 变为 3.2 vCPU 配额时的 S2，对应时延缩短率分别为 45.07% 和 54.83%。该结果支持将计算条件纳入视频压缩选择，但不替代表 I 中尚待完成的共享 1 vCPU、1 vCPU 和 4 vCPU 对照。

## D. 资源敏感性与优化需求

除链路时延、带宽和计算能力外，缓存容量与网络可用性也会影响文件送达。本案例首先围绕前三类资源分析处理与传输开销，并依据完成时间对资源变化的响应区分以下三类传输需求。

**（1）时延敏感型传输。**在文件负载较小、组装和处理开销较低的条件下，传播时延及协议交互等待可能对完成时间产生较大的相对影响。因此，小规模文本对象具有开展时延敏感性分析的价值。但当前 D2 代表事件主要受聚合等待影响，不能直接据其文件大小判定为时延敏感型；需要在保持组装策略、带宽、CPU 与丢包条件一致时，通过表 I 的 RTT 对照验证。

**（2）带宽敏感型传输。**当文件传输占完成时间的比例较高时，增加可用带宽可明显降低该部分耗时。所选图像在 2 Mbps 下的名义传输占压缩路径时间的 91.72%，体现出当前工况下较强的传输开销占比。视频同样受带宽影响，但其与直传比较时出现的收益反转说明，传输时间、压缩和解压缩开销需要共同评价。

**（3）CPU 敏感型传输。**当压缩或解压缩占比较高时，计算资源可能成为限制完成时间的重要因素。视频案例的压缩与解压缩占比随带宽提高而增大，且已有 CPU 配额对照显示最优方案发生改变，支持将视频压缩任务作为计算资源对照的重点。对于图像和小批次文本，则仍需实际测量 CPU 档位变化后的完成时间，才能判断其计算敏感程度。

上述类型描述特定工况下的资源需求，同一数据对象可同时受多项资源制约，其主要敏感资源也可能随带宽、批次规模和计算能力变化。因而，海洋监测数据的传输优化应根据实际完成时间构成，联合调整协议选择、压缩方案和缓存调度：文本需约束聚合等待，图像需权衡传输体积与处理开销，视频需结合带宽和计算条件选择压缩方案。各机制对完整送达性能的贡献由后续消融实验分别验证。
'''

notes = f'''# 案例证据与计算口径

## 主张—证据对应

| 主张 | 来源 | 可支持的范围 |
|---|---|---|
| D2 小批次压缩有效 | 当前三个样本的真实压缩记录；保存的源文件与压缩文件哈希、长度核对 | 所选 11 条观测＋表头的小批次；不代表所有文本 |
| 图片在 2 Mbps 下传输占比较高 | 实测压缩与解压缩耗时＋实际输出字节数的名义传输计算 | 所选 PNG 经 JPEG Q75 压缩；不包含画质等效验证 |
| S2 视频收益随带宽变化 | 同一视频的实测压缩与解压缩耗时＋2/4/10 Mbps 计算 | 固定 S2 配置；10 Mbps 下不优于本文直传基线，但不能证明其他压缩无效 |
| CPU 配额改变最优视频方案 | 原第二阶段报告第 5.6 节，4C-1.6V 与 4C-3.2V | 同一视频、同一 Ryzen 主机；没有重新运行 CPU 实验 |
| 组装影响完整送达时间 | FULL.csv 中匹配样本的成功记录 | 代表事件描述；三个事件不是同一网络状态的对照 |

## 原始资料

- [翻译说明]({OCEAN_ROOT.parent / 'outputs/cdn-page-4586-translation/translation_notes.md'})：用户提供的参考文件。
- [参考案例正文及资源配置表]({OCEAN_ROOT.parent / 'outputs/cdn-page-4586-translation/paper.md'})：本案例结构来源。只借鉴三类对象、时间分解和资源条件分析，未引用未提供的后续实验结论。
- [实际压缩与解压缩测量]({EXP / 'prepared/codec-measurements.json'})：三类案例的大小、耗时和完整性检查范围。
- [文件索引]({EXP / 'prepared/files.json'})：源文件、压缩文件和对象 ID。
- [FULL 文件事件记录]({EXP / 'results/FULL.csv'})：实际送达阶段时间。
- [动态链路轨迹]({EXP / 'prepared/link.csv'})：时延分位数来自 t<60 min 的 {len(link)} 个状态，按 (N−1)p 线性插值。分位数用于拟定案例对照的固定 RTT 档位，未替换已有系统消融的逐状态输入。
- [当前生成与压缩实现]({EXP / 'prepare.py'})：Gzip level 6、S2、图片压缩调用与生成速率的来源。
- [第二阶段含解压缩报告]({ROOT / '02_file_compression/weak_cpu_docker/experiment_report_with_decode.md'})：CPU 对照的来源。各视频压缩方案尚未经过统一画质指标的等效验证。

## 选择与计量

D2：筛选 logical_rows=12 的不同内容，共 {len(texts)} 个，按原始字节数和哈希排序，取中位项。文件实际有 1 行表头、11 条观测。files.json 的 record_count 是生成器切分注入的块数，不能作为观测条数。

I1：对现有九张不同图片的原始字节数排序，取第五张。V1：使用当前实验中的 4354778 B 视频。所有文件大小使用 B，带宽使用十进制 Mbps（10^6 bit/s）；不混用 MiB 与 MB。

保存的压缩与解压缩耗时为当前压缩记录的测量值，本次未重新采样，不将小数位数视为测量精度或置信区间。三类样本的哈希、计算中间量和实际事件均保存在 [计算记录]({OUT / 'case_measurements.json'})。构建脚本会验证源文件与压缩文件长度、SHA-256，以及实际事件分项和等于总时间。

图片的完整性仅为可解压缩且尺寸符合，视频为完整解压缩通过；没有 PSNR、SSIM 或 VMAF，不能报告“无损”或“相同视觉质量”。D2 的无损范围为原始字节一致。

## 论文稿的证据分配与编辑说明

- 论证链：三类输入模式 → 实际时间分解 → 名义压缩开销比较 → 带宽和计算条件改变收益 → 联合优化动机。
- 正文保留：已确认的九行资源配置表、2 Mbps 下三类对象的开销、视频高带宽下负收益、文本聚合等待以及同主机历史 CPU 对照。
- 转移到本说明：样本文件名、选择规则、原始路径、SHA-256、全部九项带宽计算和三次实际事件分项。统计与来源细节保留在计算记录中。
- 表 I 是拟定对照，不将既有不限 CPU 的测量写成 1 vCPU 条件下的结果。图像 CPU 配额试验和独立 RTT 对照尚缺，正文不作其敏感性定论。
- 未从参考论文复制网站结论或 CDF 比例；没有三类受控重复请求的分布数据，正文采用代表对象分析，不添加虚构 CDF。
- 图 2 已改为 Poor/Medium/Good 横轴与 Delay/BW/CPU 三资源系列；当前只绘制可追溯的 BW 名义计算，Delay、CPU 数据缺失保留为空值并标注待测。旧的三条开销曲线作为单独带宽比较图保留，未将其重新命名为资源曲线。
- 新增 D 节给出时延、带宽、CPU 三类需求的定义、案例依据与验证边界；原 C 节结尾合并到 D 节，避免重复联合优化动机。新类型不与三种数据形式一一绑定。
- 文稿中文撰写，面向系统与网络实验读者；单页参考的完整书目信息仍需在正式参考文献中补齐。本说明保留结构来源，不虚构作者或论文题名。

## 补充计算表

### 各带宽下的名义时延（s）

| 数据类型 | 带宽（Mbps） | 原始文件直传 | 压缩后名义传输 | 压缩与解压缩＋名义传输 | 时延缩短率 | 压缩与解压缩时间占比 |
|---|---:|---:|---:|---:|---:|---:|
{timing_table}

### 代表成功事件的实际阶段耗时（s）

| 数据对象 | 生成至组装完成 | 压缩 | 发送队列等待 | 实际网络传输 | 解压缩 | 首字节至解压缩完成 |
|---|---:|---:|---:|---:|---:|---:|
{stage_table}

三次事件发生在不同网络状态下，不作为受控跨类型对照。媒体生成至组装完成时间包含生成器按速率分块注入的过程，不是实测相机拍摄或视频采集耗时。

## 术语约定

| 术语 | 本案例定义 |
|---|---|
| 体积减少率 | (1−压缩后大小/原始大小)×100%，不称为大小比例 |
| 压缩与解压缩＋名义传输时间 | 实测压缩、解压缩与单链路 S/B 合计，不含组装、队列或协议开销 |
| 完整送达时间 | 源端首字节生成至 N3 接收、校验、解压缩完成 |
| RTT 分位数 | 固定 RTT 案例对照的参数来源，不是已完成的固定 RTT 试验结果 |
| CPU 配额 | 同一原 Ryzen 主机上 Docker 的等效 CPU 时间额度，不是实际 Raspberry Pi 测量 |

在 3600 s 前未完整送达且未明确丢失的生成数据归入 pending，可能处于组装、压缩、队列、传输或解压缩任一阶段。代表事件仅取成功项，不能用于估计全样本受限平均送达时间或丢失率。
'''

(OUT / 'assets').mkdir(exist_ok=True)
pass  # Reference image copy omitted.
(OUT / 'case_study.md').write_text(main, encoding='utf-8')
(OUT / 'evidence_notes.md').write_text(notes, encoding='utf-8')
(OUT / 'case_measurements.json').write_text(json.dumps(dict(
    samples=samples, nominal_timings=rows, actual_full_events=stages,
    link_description=dict(states=len(link), rtt_p10_ms=q10, rtt_p50_ms=q50, rtt_p90_ms=q90),
    selection=dict(d2_candidates=len(texts), image_candidates=len(images)),
    metric_scope='measured_codec_plus_single_link_serialization; direct transfer only'),
    ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Created {OUT / "case_study.md"}')
