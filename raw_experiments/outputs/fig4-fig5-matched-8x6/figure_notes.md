# Fig. 4 and Fig. 5 — matched standalone figures

Both figures use the same 8 × 6 inch canvas and the same axes rectangle as the revised Fig. 6 and Fig. 7: left 0.18, right 0.985, bottom 0.16, top 0.94. The drawn PDF frames have zero edge difference and a 4.68-inch plot height. The horizontal-axis title baselines agree within 0.01 pt, with padding adjusted for the two-line tick labels.

Fig. 4 retains all 28 wire/original ratios for the four text datasets and seven methods. Fig. 5 retains all eight image method ratios, the established calculation from supplied space-saving values, and the three-decimal labels. The inputs are byte-for-byte copies of the preceding figures’ CSVs. Bar order, fill, hatches, legends and y-axis scales are preserved.

Reproduce with python3 plot_fig4_text_compression.py and python3 plot_fig5_image_compression.py. PNGs are 2400 × 1800 px, TIFFs 4800 × 3600 px, and PDFs 576 × 432 pt. PDF/SVG text is editable. Both figures pass PDF text size (12 pt minimum) and collision audits (zero failures or warnings). The preview shows the two separately exported figures side by side. Use equal inclusion widths and identical cropping settings in LaTeX.
