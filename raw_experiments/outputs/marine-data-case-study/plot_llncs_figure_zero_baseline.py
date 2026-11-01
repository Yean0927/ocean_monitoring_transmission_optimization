"""Plot measured codec + actual ns-3 TCP resource sensitivity, mean ± SD."""
import json
import sys
from pathlib import Path

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path.home() / '.codex/skills/nature-figure/scripts'))
from audit_panel_alignment import require_matplotlib_panel_alignment

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figures/layout_figures'
OUT.mkdir(exist_ok=True)
source = json.loads((HERE / 'resource-experiment/summary.json').read_text())
assert len(source) == 27

mpl.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'STIXGeneral', 'DejaVu Serif'],
    'font.size': 8,
    'axes.titlesize': 9,
    'axes.labelsize': 8,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
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
series_specs = [('Delay', '#000000', 'D', '-'),
                ('BW', '#E50976', 'o', '--'),
                ('CPU', '#326DB1', '^', ':')]
fig, axes = plt.subplots(1, 3, figsize=(4.8031496063, 2.2047244094))
fig.subplots_adjust(left=0.10, right=0.99, bottom=0.27, top=0.87, wspace=0.50)
all_plotted = []
bottom_labels = []
legend_handles = [Line2D([], [], color=color, marker=marker, linestyle='None',
                         markersize=3.4, label=resource)
                  for resource, color, marker, _ in series_specs]
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
                linewidth=1.15, markersize=3.6)
    ax.legend(handles=legend_handles, loc='upper center', bbox_to_anchor=(0.5, 1.16),
              ncol=3, frameon=False, handlelength=0.65, handletextpad=0.25,
              columnspacing=0.35, borderaxespad=0, borderpad=0, fontsize=7)
    bottom_labels.append(ax.text(0.5, -0.30, f'({letter}) {title}',
                                transform=ax.transAxes, fontsize=9,
                                va='top', ha='center'))
    ax.set_xticks([0, 1, 2], ['Poor', 'Medium', 'Good'])
    ax.set_xlabel('Service Quality Level', labelpad=2)
    ax.set_ylabel(f'Avg. JCT ({unit})', labelpad=3)
    ax.set_xlim(-0.12, 2.12)
    maximum = max((r['mean_jct_s']+r['sd_jct_s'])*scale for r in records)
    ax.set_ylim(0, maximum*1.16)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.tick_params(direction='out', length=3, width=0.6)
    all_plotted.extend(records)

fig.canvas.draw()
bottom_anchors_pt = [artist.get_transform().transform(artist.get_position())*72/fig.dpi
                     for artist in bottom_labels]
assert max(p[1] for p in bottom_anchors_pt)-min(p[1] for p in bottom_anchors_pt) < 1.5
prefix = OUT / 'resource_sensitivity_case_study'
report = require_matplotlib_panel_alignment(
    fig, json_out=prefix.with_suffix('.alignment.json'),
    overlay_svg=prefix.with_suffix('.alignment.svg'),
    tolerance_pt=1.5, gutter_tolerance_pt=1.5,
    require_panel_labels=False, strict=True)
# The supplied reference places labels below each panel. The standard detector
# handles top-left letters only; bottom-label anchors are checked above instead.
(OUT/'bottom_panel_labels.json').write_text(json.dumps(dict(
    labels=[artist.get_text() for artist in bottom_labels],
    anchors_pt=[p.tolist() for p in bottom_anchors_pt],
    y_tolerance_pt=1.5, verdict='PASS'), indent=2))
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
