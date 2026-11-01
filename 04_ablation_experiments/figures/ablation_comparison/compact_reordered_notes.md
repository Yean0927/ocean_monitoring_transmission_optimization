# Compact three-panel revision

Question: How do eight ablation configurations differ in successful delivery, confirmed loss and mean delivery time?
Figure contract: a quantitative comparison grid using the existing Python style. The complete system has the highest supplied mean success rate and lowest loss and mean delivery time. The left panel ranks successful delivery, the center panel compares confirmed loss, and the right panel compares delay using the same category order. No significance claim is made.

All three panels share one order, descending by supplied mean successful delivery ratio: FULL, WO_CACHE, WO_PROTOCOL, ADD_COMPRESSION, WO_COMPRESSION, ADD_PROTOCOL, ADD_CACHE, BASELINE. This brings WO_CACHE immediately after FULL and leaves BASELINE last. The monotonic success curve follows from this explicit ranking. Other metrics are not independently sorted; the confirmed-loss reversal between ADD_COMPRESSION and WO_COMPRESSION is retained. Lines connect categorical configurations, rather than a continuous or temporal sequence.

Eight configurations and all 24 plotted means are preserved exactly. Pending rate remains in both source CSVs; it is excluded from the three-panel layout as previously specified. The ± fields are not used and no variability is computed or displayed, as requested. The original source CSV is preserved, and a reordered copy accompanies the plot. Reuse level: structural adaptation of the existing compact Python plot; only the category order changes.

Canvas: 8 × 3.6 inches, PNG 2400 × 1080 pixels at 300 dpi, TIFF 4800 × 2160 pixels at 600 dpi, PDF 576 × 259.2 pt. Editable PDF/SVG text, 3 pt lines, bold 13 pt axis titles and 40°/8 pt method labels follow the existing compact layout.

Suggested caption sentence: Configurations are ordered by decreasing mean successful delivery ratio, with the same order used across all panels; lines connect categorical configurations.

QA: source preflight 20 passes, 1 width warning (the requested 8-inch canvas is retained). PDF text minimum 8 pt; panel alignment passes. The axis-aligned audit reports rotated-label bounding-box intersections; an independent recovered-quadrilateral test finds zero actual text overlaps or clipping among 47 spans. All generic findings are confined to those rotated-label pairs. All three panels and the complete figure were visually inspected; exact source-value preservation, common category ordering and export dimensions were checked.

Label revision: WO_CACHE is displayed as −Cache and ADD_CACHE as +Cache. Source identifiers and mean values are preserved. Fresh PDF text and collision audits and visual inspection were completed after the label change; the compact oriented-text check again finds no actual text overlaps or clipping.
