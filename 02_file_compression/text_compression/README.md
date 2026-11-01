# 文本压缩

- [实验报告](experiment_report.md)
- [实验设计与优化说明](experiment_design_and_optimization.md)
- `images/`：上述报告实际引用的 9 张原图。
- `code/`：按包、整文件、Parquet、时间序列、最优配置选择；Rust 后端源码在 code/native_codecs。

数据默认使用 ocean/data；可用 OCEAN_DATA_DIR 覆盖。参考配置使用 ocean/data/compression_reference_results，默认新输出位于 ocean/runs/text_compression。以下命令在 ocean 根目录运行：

```sh
python -m pip install -r 02_file_compression/text_compression/code/requirements.txt
python 02_file_compression/text_compression/code/run_edge_compression_experiment.py --algorithms gzip,gorilla,chimp --numeric-codec-backend python --max-packets 2 --repeats 1 --output-dir runs/text-smoke
python 02_file_compression/text_compression/code/run_whole_file_compression_experiment.py --repeats 1 --output-dir runs/whole-file
python 02_file_compression/text_compression/code/run_best_compression_experiment.py --repeats 1 --output-dir runs/text-best
```

Parquet 优化和时间序列优化分别运行 code/run_parquet_optimization_experiment.py 和 code/run_timeseries_optimization_experiment.py。可在 code/native_codecs/ocean_numeric_codec 下执行 cargo build --release；不使用 Rust 时显式选择 Python 后端。算法测量与完整性检查保留；独立生图、生表脚本已移出。

## WPS 阅读

[实验报告 Word 阅读版](experiment_report_wps.docx) 与experiment_report.md 的正文、表格和原图对应，9 张图片已内嵌，供 WPS 阅读。原 Markdown 使用标准相对图片路径，保留便于整目录迁移；WPS 对该 Markdown 的图片加载问题尚未确认具体原因。
