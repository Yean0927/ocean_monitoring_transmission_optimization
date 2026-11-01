# Figure contract

The figures compare successful delivery ratios across six data types, showing
component removal from the full system and component addition to the baseline.
These are two separate quantitative single-panel figures as requested.

- Data: all 48 values from the supplied table; Full and Baseline appear in both comparisons.
- Figure 1: Full, Baseline, Without protocol, Without compression, Without cache.
- Figure 2: Full, Baseline, Add protocol, Add compression, Add cache.
- Horizontal axis: the five experimental configurations, in requested group order.
- Within-group bars and legend: D1, D2, D3, D4, V1, I1 in source order.
- Vertical axis: original percentages, ticks at 0, 20, 40, 60, 80, 100; upper headroom accommodates the legend.
- Template adaptation: style only; grouped bars, white background, horizontal grid, two-row legend, colored fills and white hatching.
- No aggregation, filtering, invented uncertainty, or statistical tests. Replicates and uncertainty were not supplied.
- Shared color/hatch identity across both figures: D1 blue diagonal, D2 medium blue reverse diagonal, D3 light blue dotted, D4 yellow crosshatch, V1 gray, I1 coral grid.
- Physical size: 183 × 126 mm each; PNG 300 dpi, TIFF 600 dpi; SVG and PDF retain text.
- Source data: source_data.csv. Regenerate with `python3 plot_delivery_ratio.py`.
- Each figure has one axes, so multi-panel alignment is not applicable.

Rendered QA results are stored in the corresponding JSON reports.

Final QA: both PDF collision audits passed with zero failures or warnings;
minimum rendered text is 9.5 pt. Both PNGs were inspected for correct bar order,
data, zero-height bars, legend clearance, and matching styles. Hatch strokes are
bounded vector segments, so SVG/PDF bar fills, patterns, and text are editable.
The source preflight's physical-width warning is a parsing false positive for
the expression `183 / 25.4`; the measured final PDF page is 183 × 126 mm.
