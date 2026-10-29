# Solid-style figure contract

Both comparisons retain the original Full/Baseline/Without and Full/Baseline/Add
grouping. The x axis is D1, D2, D3, D4, V1, I1. The bar and legend series are the
five configurations. No values have been changed, aggregated, or excluded.
Within each data type, the five bars are ordered from largest to smallest from
left to right. Equal values retain the original legend order through stable
sorting. Configuration colors and the legend order remain fixed across groups.
The per-figure bar_order.csv files record the displayed order and exact values.

The reference supplies styling only: teal/green/blue-gray fills, dark outlines,
bold sans-serif labels, horizontal gray grid, and exact values above bars.
All 30 bars per figure have labels, including zero values. Values remain
percentages to preserve the original measurement. No uncertainty or replicates
were supplied, so no error bars or statistical claims are added.

Final size is 264.16 × 132.08 mm to fit 30 exact two-decimal numeric labels.
Minimum font is 6.6 pt. Source data is source_data.csv; reproduce with
`python3 plot_delivery_ratio_solid.py`. PDF/SVG preserve editable text and bars;
PNG is 300 dpi and TIFF is 600 dpi. Each figure has one axes, so the multi-panel
alignment gate is not applicable. Source preflight, final PDF text and collision
audits, and inspection of both rendered PNGs are required before delivery.

Final rendered QA: both PDF collision audits pass with zero failures or warnings;
both text audits pass the 5 pt floor. Both rendered figures were inspected for
data mapping, labels, legend order, zero values, contrast, and clearance.
The source width warning is intentional: the larger canvas accommodates all
exact numeric labels and is not a claim of compliance with a specific journal.
