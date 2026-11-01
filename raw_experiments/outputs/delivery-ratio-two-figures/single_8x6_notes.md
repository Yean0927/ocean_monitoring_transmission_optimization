# Delivery-ratio figure, 8 × 6 inches

The figure uses the 24 mean and ± values in `delivery_ratio_mean_sd_input.csv`.
Each category contains all eight configurations, ordered from highest to lowest
mean. Bars preserve the established palette and white hatch patterns; axis title
and tick typography, compact in-plot single-column legend, and 8 × 6 inch canvas
follow the previous version. The legend labels use minus signs for removal
configurations and plus signs for additions.
The six module labels are displayed as “−Prot.”, “−Comp.”, “−Cache”,
“+Prot.”, “+Comp.”, and “+Cache”, with cache terminology restored as requested.
Full and Baseline retain their existing display labels; the source-data
configuration identifiers remain unchanged.

Error bars and their caps are omitted at the user's explicit request. All 24
mean values are plotted; the supplied ± values remain in the unmodified input
and exported source-data CSV. Their statistical meaning was not specified.
Bar outlines are also omitted. The in-plot legend remains lowered to the right
of the bars. The y-axis extends to 104% to provide a compact margin above the
largest mean (99.93%). No bar-top value labels are used. Bar heights use the
exact input means; no value is rounded to 100%.

PNG is 2400 × 1800 pixels at 300 dpi; TIFF is 4800 × 3600 pixels at 600 dpi.
PDF and SVG retain vector bars, patterns, axes, and text. Reproduce with
`python3 plot_single_delivery_ratio_8x6.py`.

Compact-layout revision: the 8 × 6 inch canvas uses plot bounds left=0.15,
right=0.985, bottom=0.16, top=0.94, reducing the outer right margin from 18%
to 1.5%. The categorical x-axis upper limit is reduced from 3.30 to 2.52
to tighten the open region beside the Image bars. A rendered-rectangle guard
verifies the legend does not intersect any of the 24 bars. Bar heights,
ordering, patterns, typography, and source means are unchanged.
The legend's right anchor is shifted from 0.99 to 0.96 of the axes width,
moving it left into the open region above the shorter Image bars.
