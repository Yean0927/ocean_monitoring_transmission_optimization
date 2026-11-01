# 文件压缩实验

整理日期：2026-10-26。本目录仅设以下三个实验子目录，每个目录均包含 code/、相应报告及报告直接引用的 images/。

| 子目录 | 内容 |
|---|---|
| [文本压缩](text_compression/README.md) | 按包、整文件、Parquet、Gorilla/Chimp、优化配置选择和 Rust 数值后端 |
| [视频压缩](video_compression/README.md) | FFmpeg 视频编码实验、完整报告、视频帧 PDF 和文件 8 重测报告 |
| [弱CPUdocker实验](weak_cpu_docker/README.md) | 弱 CPU 实验设计、文本含/不计解码报告、最新版视频实验报告、已找到的公共测量代码与缺失资料清单 |

已移出独立绘图、绘图布局审计、读图、合并生表和报告生成脚本，也未收录报告没有引用的多种图表导出版本。实验脚本自身产生原始测量 CSV 和实验汇总是其正常输出，仍予保留。

原 02_文件压缩 整体保留在工作区 实验代码归档/20261026_文件压缩重整前/02_file_compression，未删除文件。原先的文本 CSV 参考测量另外放在 ocean/data/compression_reference_results，供最优配置入口读取；图片编码公共接口移至 ocean/shared/image_codecs，以供系统消融引用。

当前保留 9 份报告（8 个 Markdown、1 个 PDF，含从完整报告摘录的弱 CPU 视频专题），所有直接引用的图片已核对。Docker 七算法原脚本、Dockerfile 和启动脚本未找到，详见该子目录 README；已有公共五算法代码不作为七算法原实验的替代品。
