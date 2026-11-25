# Fig. 6 and Fig. 7 — matched standalone figures

Both Matplotlib figures have an 8 × 6 inch canvas and a shared axes rectangle (left 0.18, right 0.985, bottom 0.16, top 0.94). Plot height is 4.68 inches and width is 6.44 inches. The final vector PDF frame paths were measured and match at all four edges with zero difference. Exported PNGs are 2400 × 1800 pixels; TIFFs are 4800 × 3600 pixels. PDFs are 576 × 432 points and PDF/SVG text remains editable.

Fig. 6 uses the nine existing pooled latency-reduction values for S1, S2 and S3 at 2, 4 and 10 Mbps. These are the previously saved estimates from the rounded report and ideal link-transfer model relative to direct transfer. The bar style, hatching, legend and full negative range are retained. Fig. 7 uses all seven capacity settings and all 21 supplied outcome values on a single MB axis. Cache wording, line styles and symbols are retained. Both CSVs are byte-for-byte copies of the plotting inputs. No outcomes were recalculated, transformed or dropped in this redraw.

Reproduce with python3 plot_fig6_latency_reduction.py and python3 plot_fig7_cache_capacity.py from this bundle. The alignment preview is a visual comparison of the two standalone exports. In LaTeX, use equal inclusion widths and identical cropping settings for the two PDFs.

QA: visually inspected each panel and the side-by-side preview. Both PDFs pass the text-size and collision checks; minimum text sizes are 14 and 15 pt. Fig. 7 has three intentional contained legend-background fills. The common 8-inch canvas follows the requested dimensions.
