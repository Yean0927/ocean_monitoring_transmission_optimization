# Method-comparison figures

Two independent figures, each 8 × 6 inches, compare all seven methods in the
provided reference. The 14 visible values were transcribed to source_data.csv
at the supplied three-decimal precision; no additional precision or uncertainty
was inferred. Macro F1 is dimensionless; oracle gap is displayed in Mbps.
The input column identifier is unchanged; this equivalent unit-label change
does not convert or alter the data.

This is style-only inheritance from the established delivery-ratio charts:
matching colored fills, white vector hatches, bold axes and one-column in-plot
legends. Method identities replace configuration identities, with a consistent
color and pattern in both figures. All seven methods and both measurements are
included in the supplied order. All 14 bars have bold, 12 pt value labels at
the supplied three-decimal precision. No transformations, exclusions, or
error bars are applied. The Macro F1 axis upper limit is 1.18 to keep the
Linear SVM value label clear of the legend.

Macro F1 uses an upper-right legend and oracle gap uses an upper-left legend to
keep the legends above the local data. Gridlines are interrupted at legend or
value-label bounds when they would otherwise pass through text. Both y-axes
begin at zero.

Contract: quantitative single-panel method comparisons; bars encode the
reported summaries only. The figures support comparison of the reported
metrics, not statistical significance. PNG is 2400 × 1800 px at 300 dpi;
TIFF is 4800 × 3600 px at 600 dpi; PDF and SVG preserve editable text and vector
patterns. The requested 203.2 mm width overrides common journal column widths.
Reproduce with python3 plot_method_comparison.py.

Final QA: both PDFs passed the rendered collision audit with zero failures and
zero warnings. Axis labels, method labels, legend placement and all seven bars
were visually reviewed for each figure. Both PDF pages measure 576 × 432 pt,
and both PNGs measure 2400 × 1800 px. Source preflight and PDF text audits were
run on the final exports. No statistical replication or uncertainty is supplied
in the reference; neither figure claims a significance comparison.
