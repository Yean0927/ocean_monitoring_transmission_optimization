# Text-codec comparisons, two independent 8 × 6 inch figures

Contract: single-panel quantitative grouped-bar comparisons of reported latency
reduction and wire/original ratio across four text datasets and seven algorithms.
The supplied table supplies all 28 pairs of measurements (56 plotted values).
The earlier plot supplies the full dataset/algorithm names where table columns
are visually truncated. Values are transcribed at the table's displayed precision;
there is no estimation from the heights of the earlier plot.

The same method colors, white vector hatch patterns, typography, and compact
one-column legend style are used in both figures. Method order is held constant
inside every dataset to make comparisons across datasets consistent. Bars touch
within each group. Legend positions use the empty lower-right region for latency
and upper-right region for wire/original ratio. No bar-top numbers are added to
the dense 28-bar plots. No error bars or statistical significance is inferred.

All table rows and both requested measurements are included without filtering,
normalization, rounding, or rescaling. Negative latency reduction values remain
negative; a dashed zero line distinguishes reductions from latency increases.
The wire/original ratio remains dimensionless and starts at zero. The other table
columns are fixed experimental settings, not plotted measurements.

Both outputs are 8 × 6 inches. PDF and SVG retain editable text and vector hatch
patterns. PNG is 2400 × 1800 px at 300 dpi; TIFF is 4800 × 3600 px at 600 dpi.
The requested 203.2 mm width overrides common journal column-width defaults.
Reproduce with python3 plot_text_codec_comparison.py.
