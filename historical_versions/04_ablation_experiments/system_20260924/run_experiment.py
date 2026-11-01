"""Run the five system ablations and summarize complete-file outcomes."""
from __future__ import annotations

# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT.parent / 'experiment_data/images'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT.parent / 'cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

import argparse, csv, json, math, statistics, subprocess, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=OCEAN_ROOT
NS3=OCEAN_NS3
BINARY=Path(os.environ.get('OCEAN_SYSTEM_BINARY', str(NS3/'build/scratch/ns3.42-system-ablation-optimized')))
VARIANTS=['FULL','WO_PROTOCOL','WO_COMPRESSION','WO_CACHE','BASELINE']
STREAMS=['D1','D2','D3','D4','V1','I1']
PROTOCOLS={0:'QUIC_BBR',1:'TCP_BBR',2:'TCP_CUBIC'}

def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def write(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def percentile(values,p):
    if not values:return ''
    v=sorted(values);r=(len(v)-1)*p;i=int(r);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(r-i)

def text_record_sizes(path,skip=0,encoding=None):
    raw=path.read_bytes()
    if encoding=='utf-16':
        lines=raw.decode('utf-16',errors='replace').splitlines(keepends=True)[skip:]
        return [len(line.encode('utf-16-le')) for line in lines if line.strip()]
    return [len(line) for line in raw.splitlines(keepends=True)[skip:] if line.strip()]

def summarize(output):
    summaries=[];by_stream=[];protocol_counts={};cfg=json.loads((args.prepared/'run-config.json').read_text())
    horizon=float(cfg['duration_s'])+float(cfg['drain_s'])
    definitions=json.loads((args.prepared/'files.json').read_text())
    source_dir=OCEAN_DATA
    text_dir=source_dir/"text_files" if (source_dir/"text_files").is_dir() else source_dir
    d1_sizes=text_record_sizes(text_dir/'2020_big_buoy_weather.txt',skip=1)
    d2_sizes=text_record_sizes(text_dir/'weather_data.txt',skip=1,encoding='utf-16')
    d3_sizes=text_record_sizes(text_dir/'buoy_center_wave_sensor.txt',skip=2)
    d4_lines=[line for path in sorted(text_dir.glob('*ocean_current_log-info*.log')) for line in path.read_bytes().splitlines(keepends=True)][:30]
    d4_raw=[len(line) for line in d4_lines if b'adcp_raw_data :' in line]
    d4_pre=[len(line) for line in d4_lines if b'adcp_preprocessing_data :' in line]
    video_sizes=[p.stat().st_size for p in (source_dir/'video_samples').iterdir() if p.suffix in ('.mp4','.mkv')]
    def size_summary(values):return f"均值 {statistics.mean(values):,.2f} B；范围 {min(values):,}–{max(values):,} B"
    record_size_display=[
      size_summary(d1_sizes),size_summary(d2_sizes),
      f"均值 {statistics.mean(d3_sizes):,.2f} B；完整行 {min(d3_sizes[:-1]):,}–{max(d3_sizes[:-1]):,} B；末条为 {d3_sizes[-1]} B 截断行",
      f"原始日志行 {statistics.mean(d4_raw):,.0f} B；预处理 JSON 行均值 {statistics.mean(d4_pre):,.2f} B；本轮混合行均值 {statistics.mean([*d4_raw,*d4_pre]):,.2f} B",
      f"按整段压缩；9 个样本原片 {min(video_sizes)/1e6:.2f}–{max(video_sizes)/1e6:.2f} MB/段",
      f"{cfg.get('image_representative_bytes',258715):,} B/张",
    ]
    device_counts=[
      '原始文件无设备 ID；仿真 1 路源流',
      '原始文件无设备 ID；仿真 1 路源流',
      'address 字段仅见 0x50（1 个地址）；仿真 1 路源流',
      '日志无唯一设备 ID；3 个日期文件不代表 3 台设备；仿真 1 路源流',
      '视频无相机 ID；仿真 1 路视频流',
      '图像无相机 ID；仿真 1 路图像流',
    ]
    generated_by_id=Counter()
    with (args.prepared/'events.tsv').open(newline='') as event_file:
        for event in csv.DictReader(event_file,delimiter='\t'):
            generated_by_id[int(event['id'])]+=int(event['length'])
    codec_totals=[];batch_record_counts={}
    for index,stream_name in enumerate(STREAMS):
        complete=[item for item in definitions if item['stream']==index and generated_by_id[item['id']]==item['raw_bytes']]
        batch_record_counts[stream_name]=sorted({int(item['record_count']) for item in complete})
        raw=sum(item['raw_bytes'] for item in complete);encoded=sum(item['encoded_bytes'] for item in complete)
        codec_totals.append(dict(stream=stream_name,complete_files=len(complete),raw_bytes=raw,encoded_bytes=encoded,encoded_over_raw=encoded/raw if raw else 0))
    write(output/'actual-codec-totals.csv',codec_totals)
    for variant in VARIANTS:
        rows=read(output/(variant+'.csv'))
        metrics=json.loads((output/(variant+'.csv.metrics.json')).read_text())
        counts=Counter(PROTOCOLS[int(r['protocol'])] for r in rows if int(r['protocol'])>=0)
        protocol_counts[variant]=dict(counts)
        for stream in range(7):
            group=[r for r in rows if stream==6 or int(r['stream'])==stream]
            generated=sum(int(r['generated_raw_bytes']) for r in group)
            delivered=[r for r in group if r['status']=='delivered']
            lost=[r for r in group if r['status'] in ('source_dropped','cache_evicted')]
            dbytes=sum(int(r['raw_file_bytes']) for r in delivered)
            lbytes=sum(int(r['generated_raw_bytes']) for r in lost)
            pending=generated-dbytes-lbytes
            if pending<0:raise RuntimeError('Negative pending byte accounting')
            latency=[float(r['decoded_s'])-float(r['first_s']) for r in delivered]
            waits=[float(r['tx_start_s'])-float(r['ready_s']) for r in delivered]
            transfers=[float(r['received_s'])-float(r['tx_start_s']) for r in delivered]
            # A delivery-time comparison must retain files rejected or still
            # pending at the common observation horizon. Weight each file by
            # its actually generated original bytes, including partial files.
            restricted_byte_seconds=sum(
                int(r['generated_raw_bytes'])*(
                    (float(r['decoded_s']) if r['status']=='delivered' else horizon)-float(r['first_s'])
                ) for r in group if int(r['generated_raw_bytes'])
            )
            result=dict(variant=variant,stream='ALL' if stream==6 else STREAMS[stream],
                generated_raw_bytes=generated,delivered_raw_equivalent_bytes=dbytes,
                permanently_dropped_raw_equivalent_bytes=lbytes,pending_raw_bytes=pending,
                loss_pct=100*lbytes/generated if generated else 0,
                success_delivery_pct=100*dbytes/generated if generated else 0,
                pending_pct=100*pending/generated if generated else 0,
                not_delivered_pct=100*(generated-dbytes)/generated if generated else 0,
                delivered_files=len(delivered),dropped_files=len(lost),
                restricted_mean_delivery_time_s=restricted_byte_seconds/generated if generated else '',
                success_only_mean_e2e_s=statistics.mean(latency) if latency else '',
                success_only_median_e2e_s=statistics.median(latency) if latency else '',
                success_only_p95_e2e_s=percentile(latency,.95),
                success_only_mean_queue_wait_s=statistics.mean(waits) if waits else '',
                success_only_mean_transport_s=statistics.mean(transfers) if transfers else '')
            if stream==6:result.update(metrics);summaries.append(result)
            else:by_stream.append(result)
    write(output/'summary.csv',summaries);write(output/'by-stream.csv',by_stream)
    (output/'protocol-counts.json').write_text(json.dumps(protocol_counts,indent=2))
    def fmt(x):return '—' if x=='' else f'{x:.2f}'
    lines=['# 首轮：XGBoost、真实文件压缩和 Priority-MaxF 系统消融','',
      '本轮是单随机种子、暂定组装参数的探索性运行，供下一轮调整参数。五组使用同一份源事件与链路时序。',
      '', '| 组别 | 数据成功送达率 | 已确认永久丢失率 | 截止时待完成率 | 全样本受限平均送达时间(s) |',
      '|---|---:|---:|---:|---:|']
    for r in summaries:lines.append(f"| {r['variant']} | {r['success_delivery_pct']:.2f}% | {r['loss_pct']:.2f}% | {r['pending_pct']:.2f}% | {fmt(r['restricted_mean_delivery_time_s'])} |")
    lines += ['', '## 计算公式与统计口径', '',
      r'设文件 $i$ 在源端实际生成的原始字节数为 $g_i$，首字节生成时间为 $a_i$，若 N3 完成完整文件校验与解码，完成时间为 $d_i$。总生成字节 $G=\sum_i g_i$，实验观察终点 $H=3600+300=3900\,\mathrm{s}$。',
      '', r'数据成功送达率：$R_{\mathrm{success}}=100\%\times\frac{\sum_{i:\,\mathrm{delivered}}g_i}{G}$。图像和视频经有损编码传输，分子按其对应原始文件的字节数计；未组装完成、缓存淘汰、忙时拒收和传输未完成的数据均不计入成功送达。',
      '', r'全样本受限平均送达时间：$\bar T_H=\frac{\sum_i g_i\,\tau_i}{G}$，其中 $\tau_i=d_i-a_i$（成功送达），否则 $\tau_i=H-a_i$（截至观察终点仍未送达）。成功项包含组装、编码、排队、网络传输和解码；未送达项的 $H-a_i$ 是统一观察窗口的惩罚值，不表示被丢弃的文件一直在传输，也不是它的实际完成时间。',
      '', '五组使用相同的源事件与 3900 s 观察终点，因此同一文件在各组有相同的原始字节权重与首字节时间。主表不使用只对成功文件求均值的耗时；该条件均值会因视频或图片被丢弃而看起来更短。',
    ]
    lines += ['', '## 本轮结果解读', '',
      f"FULL 成功送达率为 {summaries[0]['success_delivery_pct']:.2f}%，WO_CACHE 为 {summaries[3]['success_delivery_pct']:.2f}%。WO_CACHE 忙时直接拒收文件，全样本受限平均送达时间将这些未送达字节计到统一的观察终点，避免把拒收造成的短成功样本时间误读为更快送达。",
      '', f"WO_PROTOCOL 已确认丢失 {summaries[1]['loss_pct']:.2f}%，WO_COMPRESSION 为 {summaries[2]['loss_pct']:.2f}%。WO_PROTOCOL 比较的是本轮经本地可靠性扩展的 QUIC BBR 与 TCP CUBIC，不能将差额全部归因于 XGBoost 在线自适应。WO_COMPRESSION 同时改变字节量、编解码时间与模型输入后的协议选择，是系统模块消融。",
      '', '本轮完成生成的 D1/D3 小批次编码体积分别为原始的 '+f"{codec_totals[0]['encoded_over_raw']:.2f}、{codec_totals[2]['encoded_over_raw']:.2f} 倍，说明它们在此批次粒度压缩无收益。图片和视频的实际编码体积显著较小，主导了总体传输负载变化。",
      '', f"完整生成文件的编码总量折合 3600 s 平均 {8*sum(c['encoded_bytes'] for c in codec_totals)/cfg['duration_s']/1e6:.3f} Mbps，低于 2 Mbps 链路容量；这只是事后源负载统计，并未替代逐状态网络输入。WO_CACHE 仍会丢失，因为前一个完整文件在服务时，新到的文件没有等待位置。",
    ]
    lines += ['', '**丢失与未交付分开统计。** 本轮已确认永久丢失指 N1 无等待队列而拒收，或有限缓存淘汰；若以后出现已确认的传输终止失败，也应计入永久丢失。物理包丢失可能经重传恢复，不能直接相加为文件丢失。已生成但仍在组装、编码、等待、传输或解码的数据列为待完成，不能并入已确认永久丢失率。',
      '', '原始等价值使用对应源文件/批次的原始字节数，不使用全局平均压缩比。三个比例按原始字节加权：成功送达率 + 已确认永久丢失率 + 待完成率 = 100%。',
      '', '## 各类数据已确认丢失率', '', '| 组别 | D1 | D2 | D3 | D4 | V1 | I1 |','|---|---:|---:|---:|---:|---:|---:|']
    for v in VARIANTS:lines.append('| '+v+' | '+' | '.join(f"{next(r for r in by_stream if r['variant']==v and r['stream']==s)['loss_pct']:.2f}%" for s in STREAMS)+' |')
    lines += ['', '## 各类数据成功送达率', '', '| 组别 | D1 | D2 | D3 | D4 | V1 | I1 |','|---|---:|---:|---:|---:|---:|---:|']
    for v in VARIANTS:lines.append('| '+v+' | '+' | '.join(f"{next(r for r in by_stream if r['variant']==v and r['stream']==s)['success_delivery_pct']:.2f}%" for s in STREAMS)+' |')
    lines += ['', '各流的待完成率、字节数和文件数详见 `by-stream.csv`。', '', '## 实际采用的配置', '',
      '- 模型：用户交接包 `model/xgboost.json` + `preprocessor.joblib`；没有重训，也没有使用之前错误版本的权重。交接包校验通过，Macro F1=0.8118383933。',
      '- 三种真实协议：ns-3.42 TCP CUBIC、TCP BBR，以及 SIGNET 的 QUIC BBR 模块。不会把某协议预测替换成另一协议或吞吐系数。各协议模块版本与补丁见实验目录。QUIC 接收端会经同一链路显式请求缺失的流字节，发送端从历史载荷重发；这是非标准 QUIC 可靠性扩展，控制包也实际经过瓶颈。BBR 算法未改，但本轮不能直接视为第一阶段或标准 QUIC 的传输性能。',
      '- 拓扑 N0—N1—N2—N3：N0→N1 为固定 TCP CUBIC 的 100 Mbps 接入；N1 为应用网关，收齐原始文件并校验后开始编码；N1→N2 为 2 Mbps 瓶颈；N2→N3 为 100 Mbps。接入/出口传播延迟 0 ms，瓶颈传播延迟为时序 RTT/2，双向独立按每个当前状态的概率丢包。',
      '- 链路采用第一阶段 seed=31、0.5 min 间隔的 121 个原始状态，逐状态更新，无均值替代。源生成 3600 s，再保留末状态排空 300 s。',
      '- 组装：D1/D2/D3/D4 最长等待为 120/300/1/1800 s，原文件大小为大小上限。D1/D2 每 12 s 读取一条真实记录，D3 每 0.02 s，D4 每 120 s；实际行长直接计入生成字节数。表头按批次携带，源文件耗尽后循环回放。',
      '- 图片：九图原始大小中位数对应的真实 PNG（258715 B），1 Hz；JPEG-Q75-optimize 是本轮候选配置，没有声称最优。视频：九个实际文件顺序循环，每秒产生 195875 B，N1 收完整段后编码；本轮沿用既有 2 Mbps 配置的 S1/S2 文件选择。',
      '- 算法选择依据为 `sample_results/compression_experiment_CD_optimized_cpu100/best_algorithm_by_scenario.csv` 的 2 Mbps、CPU=100、packet_size=1448 行；该后续优化结果的 D2 为 gzip，与较早文字报告中的 Parquet+ZSTD 不同。仅采用算法选择，压缩大小和时间全部重新实测。',
      '- 文本按第二阶段代码真实执行：D1/D3 Parquet+ZSTD level 6，D2 gzip level 6，D4 Chimp 语义 ADCP、1024 行分段的 Python 实现。处理耗时来自当前 Mac；不能当作原拯救者原生实现的耗时。',
      '- 编解码对每份不同原始内容实际执行、写出产物并验证。相同内容重复出现时复用其实际编码字节及该内容的实测耗时；没有使用旧报告比率或平均比率。ns-3 按 N1 收齐时刻触发对应编码时延，传输真实产物，并在 N3 校验完整字节。',
      '- 缓存粒度为完整待发文件，50,000,000 B，按 MaxF 分数 w/(1+rho) 选择/淘汰（w∝流编号^-1.5，rho 为该流实际字节产生率×当前文件实际压缩比/当前带宽）。文件所有字节交给有限的协议发送缓冲后释放当前服务项；协议继续真实确认和重传。每种协议连接可复用，第一次握手通过真实链路。',
      '- TCP 发送/接收缓冲为 131072 B；QUIC stream 初始接收额度匹配 131072 B，随接收和 ACK 更新。N1 编码任务与 N3 解码任务使用独立计时事件，不限制并行度，未模拟 CPU 竞争。',
      '- No-Cache 只有一个正在服务的文件；忙时新到文件丢弃，无应用等待队列。所有组保留相同的组装区、一个在服务文件和协议自身缓冲；50 MB 不是节点全部 RAM 上限。组装区和等待队列峰值分别报告。',
      '- 每个待服务文件在发送开始时按该时刻状态选择协议，并在文件传输期间保持协议。为避免跨语言调用延迟，先对每个文件、每个可能链路状态用完整模型推理，仿真时读取当前状态的精确预测；这不是锚点吞吐查表。链路物理状态会在传输期间持续更新。',
      '- 模型业务特征采用文件实际字节数、1448 B 分片分布和该流实际生成率推导的名义间隔；不是瞬时 TCP 拥塞窗口的测量值。`model-inputs.json` 保存可重建的特征及逐状态预测。',
      '', '## 各类数据的生成速率', '',
      '下表速率按 3600 s 源生成阶段的原始字节统计，文本速率包含组装批次携带的表头；它表示 N1 压缩前的输入速率。单条记录大小按数据行统计，不含表头。文本批次在达到最大等待时间或原始样本文件大小上限时组装，先到者触发。压缩对象一列按本轮实际生成的完整批次统计。',
      '', '| 流/类型 | 记录或媒体生成节奏 | 单条记录/媒体对象大小 | 实际平均原始速率 | 压缩对象 | 设备数（可识别/仿真） | 当前组装设置 |','|---|---|---|---:|---|---|---|']
    cadences=[
      f"1 条记录/{cfg['record_period_s'][0]:g} s",f"1 条记录/{cfg['record_period_s'][1]:g} s",
      f"1 条记录/{cfg['record_period_s'][2]:g} s",f"1 条记录/{cfg['record_period_s'][3]:g} s",
      f"{cfg.get('video_bytes_per_second',195875):,} B/s 连续生成",f"1 张/{cfg.get('image_period_s',1):g} s，每张 {cfg.get('image_representative_bytes',258715):,} B",
    ]
    for i,(s,r,cadence) in enumerate(zip(STREAMS,cfg['raw_rates_mbps'],cadences)):
        bps=r*1e6/8
        counts=batch_record_counts[s]
        target=(f"每 {counts[0]} 条日志行合成 1 个文件" if i==3 and len(counts)==1 else
                f"每 {counts[0]} 条记录合成 1 个文本文件" if i<4 and len(counts)==1 else
                f"每批 {','.join(map(str,counts))} 条记录合成 1 个文本文件" if i<4 else
                '1 个完整源视频文件' if i==4 else '1 张原始 PNG 图片')
        assembly=(f"最长等待 {cfg['text_max_wait_s'][i]:g} s；先到最大等待或原始样本文件大小" if i<4 else
                  '收齐一个视频片段后在 N1 编码' if i==4 else '单张图片到达后在 N1 编码')
        lines.append(f'| {s} | {cadence} | {record_size_display[i]} | {bps:,.3f} B/s（{r:.9f} Mbps） | {target} | {device_counts[i]} | {assembly} |')
    lines += ['', '设备数说明：除 D3 的 address=0x50 外，原始文本/媒体没有可用于去重的传感器或相机 ID；本轮每类数据建模为 1 路源流。D4 的 3 个按日期命名的日志文件不能据此推断为 3 台设备。',
      '', 'D4 原始日志中每个采集时刻通常有一条 adcp_raw_data 和一条 adcp_preprocessing_data 日志行；本轮按日志行独立生成（间隔 120 s），每批 15 行，因此可能在 raw/preprocessing 对之间切批。表中的 9,575 B 是本轮实际抽取的两类行混合均值，不是每个 ADCP 物理观测的固定大小。',
      '', '组装与压缩发生在 N1，即本轮拓扑中的首个路由/缓存节点（可作为基站或观测网关建模）。N0 是模拟传感器侧的源节点：文本按单条记录、视频按字节段、图片按单张产生发送事件；记录是应用层单位，不等于一个网络包。N1 按文件 ID 和偏移重组，收齐压缩对象后才开始编码并向 N2 发送。准备阶段预先生成原始/编码产物用于仿真回放，不表示传感器在仿真中先把多条记录压缩成文件。']
    lines += ['', '## 本轮组装文件的实际编码体积', '', '| 类别 | 完整生成的文件数 | 原始总量(MB) | 编码总量(MB) | 编码/原始 |','|---|---:|---:|---:|---:|']
    for c in codec_totals:lines.append(f"| {c['stream']} | {c['complete_files']} | {c['raw_bytes']/1e6:.3f} | {c['encoded_bytes']/1e6:.3f} | {c['encoded_over_raw']:.3f} |")
    lines += ['', '仅统计源端在 3600 s 内完整生成的文件；视频末尾不足一段的部分不计入。这里每个组装文件都使用实际编码产物计算，没有借用整个原文件的压缩比。比值大于 1 表示本轮小批次编码反而增大了传输字节量。',
      '', '## 各类数据的全样本受限平均送达时间', '', '| 组别 | D1(s) | D2(s) | D3(s) | D4(s) | V1(s) | I1(s) |','|---|---:|---:|---:|---:|---:|---:|']
    for v in VARIANTS:
        values=[]
        for st in STREAMS:
            row=next(r for r in by_stream if r['variant']==v and r['stream']==st)
            values.append(fmt(row['restricted_mean_delivery_time_s']))
        lines.append('| '+v+' | '+' | '.join(values)+' |')
    lines += ['', '按每类实际生成的原始字节加权；未送达字节按统一观察终点 3900 s 赋予惩罚值。条件于成功文件的耗时只作为诊断数据保留在 `summary.csv` 和 `by-stream.csv` 的 `success_only_*` 列，不用于组间主比较。', '']
    lines += ['', '## 已进入传输文件的协议选择次数', '', '| 组别 | TCP CUBIC | TCP BBR | QUIC BBR |','|---|---:|---:|---:|']
    for v,c in protocol_counts.items():lines.append(f"| {v} | {c.get('TCP_CUBIC',0)} | {c.get('TCP_BBR',0)} | {c.get('QUIC_BBR',0)} |")
    lines += ['', '计数只包含已开始协议传输的文件。等待期间被缓存淘汰，或无等待队列而在忙时拒收的文件，在协议选择前就被丢弃，协议字段为 -1，因此不计入上表。WO_PROTOCOL 和 BASELINE 中实际进入传输的文件都使用 TCP CUBIC。', '']
    lines += ['', '## 结论适用范围', '',
      '本轮系统缓存项是文件，第三阶段原实验缓存项是 packet/chunk；文件在服务时不可抢占会造成大视频阻塞后续小文件。这是本轮明确记录的集成参数，不应把差异全部归因于 MaxF。',
      '', 'D1/D3 的 Parquet 是规范化字段表，D4 的 Chimp 只保留 ADCP 数值观测，不保留日志中的全部字面文本；沿用第二阶段语义口径。编码文件完整交付不等于原始 TXT/LOG 文件字节级恢复。压缩模块消融同时包含该预处理效果，不能声称严格分离了“纯编码算法”贡献。图片/视频为有损编码，此轮未评估画质；各类型压缩的数据保真范围不同。',
      '', '若 FULL 的预测在所有实际状态都相同，应解释为本次负载上模型选择该静态协议，不能证明在线切换机制有收益。若未交付主要是待完成，优先调整组装、文件服务粒度或排空时间后再比较丢失。',
      '', '## 可核查产物', '',
      '- `summary.csv`、`by-stream.csv`、`actual-codec-totals.csv`：总体、各类数据和本轮真实编码体积统计。',
      '- 每组 CSV：每个文件的组装、就绪、发送、接收、解码完成时刻及最终状态。',
      '- 每组 `.decisions.csv`：发送时的协议、原始链路状态。',
      '- `../prepared/codec-measurements.json` 与 `assets/`：实际压缩记录及二进制产物。',
      '- `../prepared/events.tsv`、`files.json`、`link.csv`：共用来源事件、文件定义与原始状态时序。',
      '']
    (output/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summaries,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,default=HERE/'prepared');p.add_argument('--output',type=Path,default=HERE/'results');p.add_argument('--summarize-only',action='store_true');p.add_argument('--workers',type=int,default=2);p.add_argument('--variants',nargs='+',choices=VARIANTS,default=VARIANTS);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    config=json.loads((args.prepared/'run-config.json').read_text())
    if not args.summarize_only:
        def run(v):
            command=[str(BINARY),f'--input={args.prepared.resolve()}',f'--output={(args.output/(v+".csv")).resolve()}',f'--variant={v}',f'--duration={config["duration_s"]}',f'--drain={config["drain_s"]}',f'--cacheBytes={config["cache_bytes"]}','--seed=31']
            print('RUN',v,flush=True);start=time.perf_counter()
            with (args.output/(v+'.log')).open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
            if 'QUIC_ABORT' in (args.output/(v+'.log')).read_text():raise RuntimeError(v+' encountered a QUIC connection abort; do not summarize as a valid ablation')
            print('DONE',v,round(time.perf_counter()-start,1),'wall seconds',flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(run,args.variants))
    summarize(args.output)
