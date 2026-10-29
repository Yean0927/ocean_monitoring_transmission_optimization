# 视频延迟降低比例图：数字化近似预览

状态：原始实验 CSV 未找到，本目录中的图是从用户参考图提取坐标后重绘的近似预览，不能替代原始实验数据。

## 图与指标

已按视频报告表格确认：用户指定的 file8 是 `5cf7af68d381d7cb80e5567444e894c2.mp4`。
旧汇总图按文件名排序，该样本位于第 6 个子图；这是排序差异，样本身份不变。
报告第 8 行的 S0–S3 压缩比为 1.000、0.148、0.112、0.107，已直接从 Markdown 导出到 `file8_report_compression_ratios.csv`。
压缩比表没有编码/解码耗时及逐带宽延迟数值，不能用它重算延迟降低比例；绘图数据继续逐行标记为原图数字化近似值。
横轴是带宽 2、4、10 Mbps，纵轴是 Latency reduction (%)，即相对 S0 原始直传的延迟降低比例。
它不是文件体积压缩率图；负值表示相对直传延迟增加。
汇总图标明分片大小为 4096 bytes。原始结果缺失，因此无法重新核验编码/解码耗时的具体口径。

## 文件

- `file8_latency_reduction_digitized.png`：明确对应 file8 的最新结果，4800×3600 像素，600 dpi。
- 同名 PDF 与 SVG：矢量文件，文字可编辑。
- `digitized_plot_data.csv`：12 个数字化近似点，逐行标记数据来源。
- `reference.png`：未修改的用户参考图。
- `digitization.json`：图像坐标、刻度校准、提取方法及近似误差说明。
- `plot_video_latency.py`：CSV 驱动的绘图脚本，可接入原始实验结果。
- `source-preflight.json`、`text-audit.json`、`*.collision-audit.json`：最终版本检查结果。

## 样式与检查

画布固定 `figsize=(8, 6)`，导出时不紧裁剪，PDF 实测页面为 576×432 pt，即 8×6 英寸。
横纵轴标签为 20 pt 粗体，刻度为 16 pt 粗体，四条曲线线宽为 3 pt，零值虚线为 2 pt。
颜色、标记形状及 S0–S3 曲线均保留；图例按用户标注移至绘图区内左下角，分为两列，字号 12 pt。图例覆盖区域内的背景网格线已清除，曲线数据不变。
PDF 文字字号检查通过，最小字号 12 pt；碰撞检查无 FAIL/WARN。
这是单面板图，面板对齐检查不适用。
源代码检查的宽度提示来自用户指定的 8 英寸；另一个提示是未导出 TIFF，本次交付 PNG、PDF、SVG。
已逐项查看标签、图例、全部曲线及负值范围，未发现截断或遮挡。
没有添加无法从参考图获知的误差棒或重复测量信息。

## 更换为原始实验数据

CSV 须包含 `video_name, algorithm, bandwidth_mbps, packet_size_bytes, latency_reduction_pct`。
使用以下命令可生成单独的原始数据版本，不覆盖数字化预览：

```sh
python3 plot_video_latency.py --input-csv /path/to/end_to_end_results.csv --output-stem fig9_latency_reduction_original_data
```

脚本验证 S0–S3 各方案在 2、4、10 Mbps 下均有唯一数据点；缺失或重复时直接报错，不进行隐式平均或省略。

## 数据完整性边界

当前提取的是图中全部四条曲线的 12 个点，无曲线省略。
颜色像素中位数经坐标刻度线性校准后得到近似值；约 1 个百分点的读图误差只用于提示数值精度，并非统计置信区间或严格误差上限。
实验脚本引用的视频正式结果目录在当前同步包中缺失；本目录未新建或伪造该原始结果文件。
