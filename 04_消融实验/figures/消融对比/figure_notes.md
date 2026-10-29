# Ablation line figures

All plotted values are the means shown before `±` in the supplied table. The reported `±` values are neither plotted nor used to calculate new statistics; no error bars or other variability encodings are shown. The source CSV retains all four mean metrics, including pending rate. To preserve the previously selected figure designs, the charts show successful delivery rate, confirmed loss and average delivery time.

The source values are kept as provided. Baseline is moved to the far right in both views; the other configurations retain their relative order. Lines connect the categorical configurations and do not imply interpolation.

## Dual-axis view

`dual_axis_8x6` places Success Rate and Confirmed Loss on the left Rate (%) axis, and Average delivery time on the right Avg. Latency (s) axis. Blue circles, orange squares and purple triangles distinguish the three lines.

## Three-panel view

`three_panel_8x6` contains three horizontally arranged panels for successful delivery ratio, confirmed loss and average delivery time. `three_panel_8x3p6` is the compact manuscript-layout alternative. Its shortened method labels are rotated 40° to retain readability while reducing page height.

## Export and checks

The `*_8x6` figures are exactly 8 × 6 inches (2400 × 1800 px at 300 dpi; PDF page 576 × 432 pt). The compact three-panel alternative is 8 × 3.6 inches (2400 × 1080 px at 300 dpi; PDF page 576 × 259.2 pt). Each variant is exported as PNG, TIFF, PDF and SVG; vector files preserve editable text. Line widths are 3 pt, axis titles are bold, and Baseline appears last.

The plotting source preflight reports 20 passes and one target-width warning: 8 inches is wider than common single/double-column defaults. PDF text-size, collision and panel-alignment audits pass for the two 8 × 6 figures. For the compact rotated-label figure, the axis-aligned audit reports bounding-box overlaps; the separate oriented-text audit checks the actual rotated glyph quadrilaterals and passes with zero overlaps or clipping (47 text spans).
