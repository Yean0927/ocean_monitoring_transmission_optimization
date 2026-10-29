"""Render the final experiment's source-rate configuration as a Chinese table."""
from pathlib import Path
import csv
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
BASE = ROOT / 'system-ablation-20260928-table-rates'
cfg = json.loads((BASE / 'prepared/run-config.json').read_text())
provenance = json.loads((BASE / 'validation/repeated-five-seeds-rto-fixed-20261015/provenance.json').read_text())
assert Path(provenance['prepared']).resolve() == (BASE / 'prepared').resolve()
assert cfg['duration_s'] == 3600 and cfg['drain_s'] == 0
NAMES = ['D1 大浮标气象数据', 'D2 普通气象数据', 'D3 波浪传感器数据',
         'D4 ADCP 海流数据', 'V1 海洋视频数据', 'I1 图片数据']
rows = []
records = []
for i, (name, r) in enumerate(zip(NAMES, cfg['user_rate_table'])):
    actual = cfg['generated_raw_bytes'][i] * 8 / cfg['duration_s'] / 1e6
    assert abs(actual - cfg['raw_rates_mbps'][i]) < 1e-12
    rows.append([name, f"{r['record_bytes']:,}",
                 f"{r['record_period_s']:g} s/次", f"{r['sensors']} 个",
                 f"{r['target_mbps']:.9f}".rstrip('0').rstrip('.')])
    records.append(dict(stream=r['stream'], reference_record_bytes=r['record_bytes'],
                        reference_record_period_s=r['record_period_s'],
                        reference_sensors=r['sensors'], simulated_aggregate_flows=1,
                        target_rate_mbps=r['target_mbps'], actual_rate_mbps=actual,
                        generated_raw_bytes=int(cfg['generated_raw_bytes'][i]), duration_s=3600))
with (OUT / 'source_generation_rates.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
headers = ['数据流', '参考原始大小\n(B)', '参考记录频率', '参考传感器数量', '目标生成速率\n(Mbps)']
md = ['# 最后一轮系统消融实验的数据生成配置', '',
      '适用于最终重传定时器修复版的五种子、八组系统消融实验。观察窗口为 3600 s，各组共用相同源事件。', '',
      '实际执行以目标 Mbps 列为每类数据的合计源速率。参考记录大小、参考频率和参考设备数来自给定参数表，不代表当前生成器逐项独立实现的设备采样设置。', '',
      '| 数据流 | 参考原始大小 (B) | 参考记录频率 | 参考传感器数量 | 目标生成速率 (Mbps) |',
      '|:--|--:|--:|--:|--:|']
md += ['| ' + ' | '.join(r) + ' |' for r in rows]
md += ['', '## 实际生成量校验', '',
       '| 数据流 | 3600 s 实际生成原始字节数 (B) | 实际平均生成速率 (Mbps) |', '|:--|--:|--:|']
md += [f"| {r['stream']} | {r['generated_raw_bytes']:,} | {r['actual_rate_mbps']:.9f} |" for r in records]
md += ['', '说明：', '',
       '- 六类数据在模拟器中各合并为一路；文本没有为每台参考传感器单独创建连接。',
       '- D1–D4 保留本地真实记录内容，按实际字节长度与目标速率安排到达；不是按参考频率固定生成表列长度的记录。',
       '- D2 在配置中的参考频率为 12 s/次，截图为 60 s/次；实际执行仍以 0.000028665 Mbps 为准。43 B、12 s、5 台不能共同推导出这个目标速率。',
       '- V1 按 208,481 B/s 分段生成，9 个真实视频文件依次循环；4,354,778 B 是参考大小，1 s/次不表示每秒生成一个完整视频。',
       '- I1 使用九张图片中位数对应的实际图片，大小为 258,715 B，每 5 s 启动一张图片的数据生成。',
       '- 实测速率 = 3600 s 内实际生成原始字节数 × 8 / 3600 / 10^6；首末分段及观察窗口截止造成目标与实测的轻微差异。',
       '- 表内前三类文本的平均实际记录大小分别为 78.13、90.01、130.38 B；D4 本轮混合日志行均值为 9,575.20 B。参考大小不能作为本轮真实记录长度。']
(OUT / 'source_generation_rates.md').write_text('\n'.join(md) + '\n', encoding='utf-8')

font_file = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
font_manager.fontManager.addfont(font_file)
family = font_manager.FontProperties(fname=font_file).get_name()
plt.rcParams.update({'font.family': family, 'font.size': 13.5,
                     'pdf.fonttype': 42, 'svg.fonttype': 'none'})
fig, ax = plt.subplots(figsize=(13.5, 4.25))
fig.subplots_adjust(left=0.008, right=0.992, top=0.98, bottom=0.02)
ax.set_axis_off()
table = ax.table(cellText=rows, colLabels=headers, loc='center', cellLoc='right',
                 colWidths=[0.27, 0.19, 0.18, 0.17, 0.19], bbox=[0, 0, 1, 1])
table.auto_set_font_size(False)
table.set_fontsize(14)
for (r, c), cell in table.get_celld().items():
    cell.set_facecolor('white')
    cell.set_edgecolor('#D1D1D1')
    cell.set_linewidth(0.8)
    cell.PAD = 0.03
    if r == 0:
        cell.set_text_props(weight='bold', ha='left' if c == 0 else 'center', fontsize=14)
    elif c == 0:
        cell.set_text_props(ha='left')
fig.canvas.draw()
cells = table.get_celld()
header_y = cells[0, 0].get_y()
ax.plot([0, 1], [header_y, header_y], color='#4B4B4B', linewidth=1.8,
        transform=ax.transAxes, clip_on=False)
for r in range(1, 6):
    y = cells[r, 0].get_y()
    ax.plot([0, 1], [y, y], color='#BFBFBF', linewidth=1.3, transform=ax.transAxes, clip_on=False)
fig.savefig(OUT / 'source_generation_rates.png', dpi=200)
fig.savefig(OUT / 'source_generation_rates.pdf')
fig.savefig(OUT / 'source_generation_rates.svg')
plt.close(fig)
(OUT / 'provenance.json').write_text(json.dumps({
    'config': str((BASE / 'prepared/run-config.json').relative_to(ROOT)),
    'experiment': 'repeated-five-seeds-rto-fixed-20261015',
    'definition': 'Per-class total source rate; reference record fields are not independently enforced.',
    'all_six_streams_included': True,
    'actual_rates_from_generated_bytes': True,
}, indent=2) + '\n')
print('\n'.join(md[:13]))
