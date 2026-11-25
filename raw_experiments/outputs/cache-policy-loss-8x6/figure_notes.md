# Figure contract

- Question: how do the five supplied cache policies distribute data loss across six streams?
- Evidence: one grouped bar chart, with all 30 requested stream percentages and the table's category and policy order preserved.
- Archetype: quantitative comparison, single panel.
- Backend: Python / matplotlib, using the saved project preference.
- Canvas: exactly 8 × 6 inches; PNG at 300 dpi, TIFF at 600 dpi, editable SVG and PDF.
- Style: bold Arial axes and ticks, white background, light horizontal grid, blue/grey/pastel palette, white vector textures and a compact vertical in-plot legend.
- Mapping: table columns D1–I1 → x-axis; Policy → legend; cell value → bar height in percent. Total is excluded at the user's explicit request; the original CSV remains intact (35 source values, 30 plotted values).
- The supplied table is authoritative. Its Priority-Utility row is retained exactly as supplied even though an existing report assigns these values to a differently named policy.
- No rescaling, interpolation, sorting or invented uncertainty. Replicates, confidence intervals and statistical tests were not supplied.
- Interpretation boundary: descriptive loss-rate comparison only; the supplied table does not establish statistical significance.
- Alignment: single panel, not applicable. Run source, rendered text and collision audits and visually inspect the exports before delivery.

## Final QA

- Visual check: all six categories and five full policy labels are readable; no clipping or legend/bar overlap. All 30 bars retain their supplied values. The x range is tightened to −0.55–5.55 for symmetric outer margins; the legend sits above V1 between the tall D4 and I1 bars.
- Source preflight: 0 FAIL, 1 WARN. Width warning accepted because 8 inches (203.2 mm) was explicitly requested.
- PDF glyph audit: minimum 11 pt, no text below 5 pt.
- PDF collision audit: PASS, 0 FAIL and 0 WARN.
- Canvas verified: PDF 576 × 432 pt; PNG 2400 × 1800 pixels; TIFF 4800 × 3600 pixels.
