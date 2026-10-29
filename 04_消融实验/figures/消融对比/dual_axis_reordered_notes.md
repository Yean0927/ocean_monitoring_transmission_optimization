# Dual-axis ablation comparison

Question: How do eight ablation configurations compare in successful delivery, confirmed loss and average delivery time? The full system has the highest supplied mean successful delivery ratio and lowest loss and time. This is a single quantitative comparison plot with two vertical axes. No significance claim is made.

The shared category order is FULL, WO_CACHE, WO_PROTOCOL, ADD_COMPRESSION, WO_COMPRESSION, ADD_PROTOCOL, ADD_CACHE, BASELINE, matching the reordered compact three-panel plot. The order is decreasing mean successful delivery ratio. All eight configurations and all 24 plotted means are preserved; no smoothing, interpolation, normalization or uncertainty calculation is performed. The previously unplotted pending-rate metric remains in the source CSV. The supplied ± fields are omitted as requested. Lines connect categorical configurations; the monotonic success curve follows from the explicit ranking.

Success Rate (blue circles, solid) and Confirmed Loss (orange squares, dashed) use the left Rate (%) axis. Average delivery time (purple triangles, dash-dot) uses the right Avg. Latency (s) axis. The two scales have aligned zeros. The palette, markers and means match the compact figure.

Exports: exactly 8 × 6 inches, PNG 2400 × 1800 px at 300 dpi, TIFF 4800 × 3600 px at 600 dpi, PDF 576 × 432 pt, editable PDF/SVG text. Axis titles are 20 pt bold, lines 3 pt, and abbreviated method labels are rotated 40°.

Suggested caption sentence: Configurations are ordered by decreasing mean successful delivery ratio. Success Rate and Confirmed Loss use the left axis; average delivery time uses the right axis.

QA: visually inspected the complete figure and both axes; all 24 values are mapped directly from the supplied mean columns. PNG/PDF export dimensions verified. Source preflight: 20 passes and one width warning (the requested 8-inch canvas is retained). PDF text minimum is 11.5 pt. Rendered collision audit passes with zero failures or warnings. Alignment audit records a single plot area with the shared twin axis excluded, so multi-panel alignment is not applicable.

Label revision: WO_CACHE is displayed as −Buffer and ADD_CACHE as +Buffer. Source identifiers and mean values are preserved. Fresh PDF text and collision audits and visual inspection were completed after the label change; the compact oriented-text check again finds no actual text overlaps or clipping.
