# 视频压缩

- [完整实验报告](实验报告.md)：2026-10-26 同步用户提供的最新版，包含常规视频实验与 Docker 弱 CPU 视频结果。
- [Docker 弱 CPU 视频专题报告](../弱CPUdocker实验/视频压缩实验报告.md)：从最新版原稿摘录，方便按 CPU 实验查阅。
- [文件 8 重新测量报告](文件8重新测量报告.md)：2026-10-18 的独立新测量，不能替换其他视频的历史结果。
- [视频帧压缩实验报告 PDF](视频帧压缩实验报告.pdf)
- `images/`：报告直接引用的 image-10.png、image-13.png 和 file8_latency_recomputed.png。
- `code/run_video_compression_experiment.py`：唯一视频测量入口，含 S0/S1/S2/S3 实际转码、完整解码检查及计时。

需准备支持相应编码器的 FFmpeg。以下命令在 ocean 根目录运行：

```sh
python 02_文件压缩/视频压缩/code/run_video_compression_experiment.py --input-dir data/视频样本 --output-dir runs/video --ffmpeg /absolute/path/to/ffmpeg --schemes S0,S1,S2 --repeats 3
```

支持 --max-videos、--scheme-repeats、--resume；文件 8 身份以源文件名为准，见重测报告。没有保留独立绘图、读图重绘、表格生成或报告生成脚本；PDF 原稿整体保留，其内嵌图片不需要另行提取。
