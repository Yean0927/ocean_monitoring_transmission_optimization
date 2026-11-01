"""Plot the three representative payloads from saved codec and size measurements."""
import json
import sys
from pathlib import Path

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

sys.path.insert(0, str(Path.home() / '.codex/skills/nature-figure/scripts'))
from audit_panel_alignment import require_matplotlib_panel_alignment

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
source = json.loads((HERE / 'case_measurements.json').read_text())

mpl.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial Unicode MS', 'Arial', 'DejaVu Sans'],
    'font.size': 8,
    'axes.titlesize': 9,
    'axes.labelsize': 8,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 8,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.7,
    'pdf.fonttype': 42,
    'svg.fonttype': 'none',
    'savefig.facecolor': 'white',
})

# One recorded payload per type, three bandwidth calculations, no replicate mean.
panel_specs = [('D2', '文本 D2', 1000, 'ms'),
               ('V1', '视频 V1', 1, 's'),
               ('I1', '图片 I1', 1, 's')]
series_specs = [('direct_s', '原始直传', '#252525', 'D', '-'),
                ('total_s', '压缩＋传输＋解压缩', '#D52678', 'o', '--'),
                ('codec_s', '压缩＋解压缩', '#356FA6', '^', ':')]
fig, axes = plt.subplots(1, 3, figsize=(7.0866141732, 3.0708661417))
fig.subplots_adjust(left=0.075, right=0.975, bottom=0.28, top=0.76, wspace=0.43)
all_plotted = []
for letter, ax, (stream, title, scale, unit) in zip('abc', axes, panel_specs):
    records = sorted((r for r in source['nominal_timings'] if r['stream'] == stream),
                     key=lambda r: r['bandwidth_mbps'])
    assert [r['bandwidth_mbps'] for r in records] == [2, 4, 10]
    assert all(abs(r['total_s']-r['transfer_s']-r['codec_s']) < 1e-12 for r in records)
    for key, label, color, marker, linestyle in series_specs:
        ax.plot([0, 1, 2], [r[key]*scale for r in records],
                label=label, color=color, marker=marker, linestyle=linestyle,
                linewidth=1.3, markersize=3.8)
    ax.set_title(title, pad=11)
    ax.text(-0.02, 1.10, letter, transform=ax.transAxes, fontweight='bold',
            fontsize=9, va='bottom', ha='left')
    ax.set_xticks([0, 1, 2], ['差\n2 Mbps', '中等\n4 Mbps', '好\n10 Mbps'])
    ax.set_xlabel('带宽资源质量等级', labelpad=6)
    ax.set_ylabel(f'名义完成时间（{unit}）', labelpad=4)
    ax.set_xlim(-0.12, 2.12)
    maximum = max(r['direct_s']*scale for r in records)
    ax.set_ylim(0, maximum*1.10)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.tick_params(direction='out', length=3, width=0.6)
    if stream == 'V1':
        ax.text(0.53, 0.66, '10 Mbps 时\nS2 慢 2.81%', transform=ax.transAxes,
                fontsize=7, ha='left', va='center', color='#252525')
    all_plotted.extend(records)

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.985),
           ncol=3, frameon=False, columnspacing=1.5, handlelength=2.4)
fig.canvas.draw()
prefix = OUT / 'bandwidth_case_study'
report = require_matplotlib_panel_alignment(
    fig, json_out=prefix.with_suffix('.alignment.json'),
    overlay_svg=prefix.with_suffix('.alignment.svg'),
    tolerance_pt=1.5, gutter_tolerance_pt=1.5,
    require_panel_labels=True, strict=True)
fig.savefig(prefix.with_suffix('.pdf'))
fig.savefig(prefix.with_suffix('.svg'))
fig.savefig(prefix.with_suffix('.png'), dpi=300)
fig.savefig(prefix.with_suffix('.tiff'), dpi=600)
(OUT / 'source_data.json').write_text(json.dumps(dict(
    records=all_plotted, panel_order=['D2', 'V1', 'I1'],
    measures=[key for key, *_ in series_specs],
    uncertainty='none: one recorded representative payload per type; deterministic size/B calculation',
    direct_scope='original bytes/B; excludes original media decoding',
    compressed_scope='measured compression + compressed bytes/B + measured decompression',
    exclusions='No RTT or CPU-grade curves: the proposed three-grade measurements are unavailable.'),
    ensure_ascii=False, indent=2), encoding='utf-8')
plt.close(fig)
print(f'Created {prefix.name}: PDF, SVG, PNG, TIFF; panel alignment {report["verdict"]}')
