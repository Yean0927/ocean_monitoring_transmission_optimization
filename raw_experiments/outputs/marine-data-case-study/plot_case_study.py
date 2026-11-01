"""Plot measured codec + actual ns-3 TCP resource sensitivity, mean ± SD."""
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
source = json.loads((HERE / 'resource-experiment/summary.json').read_text())
assert len(source) == 27

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

panel_specs = [('D2', 'Text (D2)', 1, 's'),
               ('V1', 'Video (V1)', 1, 's'),
               ('I1', 'Image (I1)', 1, 's')]
series_specs = [('Delay', '#252525', 'D', '-'),
                ('BW', '#D52678', 'o', '--'),
                ('CPU', '#356FA6', '^', ':')]
fig, axes = plt.subplots(1, 3, figsize=(7.0866141732, 3.0708661417))
fig.subplots_adjust(left=0.075, right=0.975, bottom=0.28, top=0.76, wspace=0.43)
all_plotted = []
for letter, ax, (stream, title, scale, unit) in zip('abc', axes, panel_specs):
    records = [r for r in source if r['stream'] == stream]
    assert len(records) == 9
    for resource, color, marker, linestyle in series_specs:
        selected = [next(r for r in records if r['resource'] == resource and r['quality'] == q)
                    for q in ['Poor', 'Medium', 'Good']]
        assert all(r['n'] == 5 for r in selected)
        values = [r['mean_jct_s']*scale for r in selected]
        uncertainty = [r['sd_jct_s']*scale for r in selected]
        ax.errorbar([0, 1, 2], values, yerr=uncertainty, capsize=2, elinewidth=0.8,
                label=resource, color=color, marker=marker, linestyle=linestyle,
                linewidth=1.3, markersize=3.8)
    ax.set_title(title, pad=11)
    ax.text(-0.02, 1.10, letter, transform=ax.transAxes, fontweight='bold',
            fontsize=9, va='bottom', ha='left')
    ax.set_xticks([0, 1, 2], ['Poor', 'Medium', 'Good'])
    ax.set_xlabel('Service Quality Level', labelpad=6)
    ax.set_ylabel(f'Avg. JCT ({unit})', labelpad=4)
    ax.set_xlim(-0.12, 2.12)
    maximum = max((r['mean_jct_s']+r['sd_jct_s'])*scale for r in records)
    ax.set_ylim(0, maximum*1.16)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.tick_params(direction='out', length=3, width=0.6)
    all_plotted.extend(records)

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.985),
           ncol=3, frameon=False, columnspacing=1.5, handlelength=2.4)
fig.canvas.draw()
prefix = OUT / 'resource_sensitivity_case_study'
report = require_matplotlib_panel_alignment(
    fig, json_out=prefix.with_suffix('.alignment.json'),
    overlay_svg=prefix.with_suffix('.alignment.svg'),
    tolerance_pt=1.5, gutter_tolerance_pt=1.5,
    require_panel_labels=True, strict=True)
fig.savefig(prefix.with_suffix('.pdf'))
fig.savefig(prefix.with_suffix('.svg'))
fig.savefig(prefix.with_suffix('.png'), dpi=300)
fig.savefig(prefix.with_suffix('.tiff'), dpi=600)
(OUT / 'resource_source_data.json').write_text(json.dumps(dict(
    records=all_plotted, panel_order=['D2', 'V1', 'I1'],
    resources=[key for key, *_ in series_specs],
    quality_levels=['Poor', 'Medium', 'Good'],
    resource_series={stream: {
        resource: [next(r['mean_jct_s'] for r in all_plotted
                       if r['stream'] == stream and r['resource'] == resource and r['quality'] == q)
                   for q in ['Poor', 'Medium', 'Good']]
        for resource, *_ in series_specs} for stream, *_ in panel_specs},
    uncertainty='mean ± sample SD; n=5 technical repetitions per condition; paired codec repeats across Delay/BW',
    compressed_scope='N1 complete raw file to N3 checked receipt and measured decompression completion; actual TCP CUBIC stack in ns-3',
    limitations='single representative object per type; zero configured random packet loss; shared CPU emulated by 0.5 CPU-s/s quota; no visual quality equivalence measurement',
    trials_source=str(HERE/'resource-experiment/trials.json')),
    ensure_ascii=False, indent=2), encoding='utf-8')
plt.close(fig)
print(f'Created {prefix.name}: PDF, SVG, PNG, TIFF; panel alignment {report["verdict"]}')
