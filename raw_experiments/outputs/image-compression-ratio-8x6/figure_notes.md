# Image compression ratio, 8 × 6 inches

Question: what fraction of original size remains for each of the eight methods?
Single-panel quantitative comparison, Python backend, all eight input methods
retained in the original order. The requested ratio follows the reference's
Wire/Original definition: compressed size / original size = 1 − saving / 100.
This is not original size / compressed size.

Source percentages are preserved in source_data.csv alongside the derived ratio.
Their precision is limited to the provided one-decimal percentages; ratios are
displayed to three decimal places without a percent sign. No exclusions,
statistical tests, or invented uncertainty. Values are descriptive, with no
replicates supplied. All eight values are labeled above the bars.

Style-only inheritance from the existing chart: bold Arial labels, established
method colors and vector hatches, light horizontal grid, compact vertical
legend. Move the legend to the upper right to clear the high first three bars.
Canvas remains exactly 8 × 6 inches. Export editable PDF/SVG, PNG at 300 dpi,
and TIFF at 600 dpi. Single-panel alignment is not applicable. Inspect all labels,
legend clearance, and final geometry; run source, text and PDF collision audits.

## Final QA

- Visual inspection: all eight methods and all eight three-decimal value labels are readable; the upper-right legend clears every bar and label.
- Rendered collision audit: PASS, 0 FAIL, 0 WARN.
- PDF text audit: minimum 12 pt; no glyphs below 5 pt.
- Source width warning is accepted because the requested established canvas is 8 × 6 inches.
- Export dimensions verified: PDF 576 × 432 pt, PNG 2400 × 1800 px, TIFF 4800 × 3600 px.
