# Cache capacity: style synchronized with delivery-ratio figure

The single-axis figure plots all seven settings and all 21 outcome values from source_data.csv. Curves, markers, colors, data ranges, and the 15 pt in-plot legend retain their previous definitions. Horizontal axis: Cache capacity (MB). Vertical axis: Volume (MB). No data are normalized, excluded, interpolated, or altered.

Canvas: exactly 8 × 6 inches. Plot bounds are left=0.15, right=0.985, bottom=0.16, top=0.94, matching the current delivery-ratio figure. All four frame edges have color #2C2C2C and width 1.2 pt. Axis titles use Arial Bold, 20 pt, with horizontal/vertical label padding of 9/8 pt. Tick labels use 16 pt bold; tick width/length/padding are 1.2/4/5 pt. The outcome-specific axis wording is retained.

Final rendered geometry verification: frame-edge differences are zero points. The horizontal axis-title baseline differs from the reference by 0.03125 pt due to glyph metrics; the vertical axis-title x baseline is identical. Font family, weight, and title size match. See delivery_style_sync.json for measurements.

Exports: PNG 2400 × 1800 px at 300 dpi; TIFF 4800 × 3600 px at 600 dpi; PDF 576 × 432 pt; editable PDF/SVG text. The separate dual-axis variant is retained.

Final QA: whole figure visually inspected; text audit and collision audit pass. Three contained fills are the intentional legend text on its white background. The source preflight's requested-width warning is accepted because the user specified an 8-inch canvas.

Terminology revision: the horizontal title is Cache capacity (MB), and the third legend entry is Peak cache occupancy. Source column identifiers and all 21 numerical outcomes are preserved. Fresh text and collision audits pass after regenerating all four formats; the minimum PDF text size is 15 pt. All visible labels were verified to contain no remaining buffer wording, and the final figure was visually inspected.
