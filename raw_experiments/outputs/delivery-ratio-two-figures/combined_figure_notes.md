# Combined figure contract

Question: how do individual components affect delivery across text, video, and
image data? Panel a removes components from the full system; panel b adds
components to the baseline. The paired comparisons are distinct perturbations.

The figure retains the user's solid-color style, exact labels, and descending
left-to-right order within each category. All configuration colors stay fixed.
The two panels share axis limits, ticks, category order, and physical plot sizes.
Bar width is 0.076 category units, versus 0.153 previously, with 0.145 center
spacing to make the narrower bars visibly distinct. The combined canvas is
350.52 × 129.54 mm. No stochastic uncertainty or replicates were supplied.

Text pools D1–D4 by actual raw-byte counts:

`100 × sum(delivered_raw_equivalent_bytes) / sum(generated_raw_bytes)`

The common Text denominator is 23,106,262 generated raw bytes. This preserves
the experiment's byte-based successful-delivery definition. Pending and lost
bytes stay in the denominator. It is not the arithmetic mean of four rates.
Video and Image use the same original measurement for V1 and I1. Source count
records reproduce all 48 supplied table percentages at two-decimal precision.
The counts are preserved in source_counts.csv; all 24 pooled output values and
their numerators/denominators are in combined_text_video_image.source_data.csv.

Text success rates (rounded only for display):

| Configuration | Text success (%) |
|---|---:|
| Full | 99.93 |
| Without protocol | 99.93 |
| Without compression | 98.78 |
| Without cache | 78.72 |
| Baseline | 13.51 |
| Add protocol | 27.97 |
| Add compression | 46.69 |
| Add cache | 99.90 |

Source: the final complete eight-configuration experiment, verified against
the table. No abandoned validation run is used. Source data are preserved;
only the user-requested D1–D4 grouping is applied. Sorting is stable for ties.

Reproduce with `python3 plot_combined_delivery_ratio.py`. Vector PDF/SVG retain
editable text and bar geometry. PNG is 300 dpi; TIFF is 600 dpi. Required QA:
final rendered panel alignment, source preflight, final PDF glyph and collision
audits, and panel-by-panel PNG inspection.

Final QA: panel alignment passed (shared tops, bottoms, heights and label
anchors); both plot areas have equal width. Final PDF collision audit has zero
failures or warnings; minimum text is 6.6 pt. Source preflight has no failures;
the nonstandard width warning is documented because this is a combined canvas
with exact numeric labels, not a journal-specific submission. Both panels and
the complete PNG were visually inspected after the final spacing adjustment.
