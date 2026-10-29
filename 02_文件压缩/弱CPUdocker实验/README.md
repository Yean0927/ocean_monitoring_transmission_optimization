# 弱CPU Docker 实验

- [视频压缩实验报告](视频压缩实验报告.md)：最新版视频报告的 Docker 弱 CPU 章节，包含 Host-Docker 与 Edge-XL 两个正式 profile，采用计入解码的时延口径；本节无图片引用。
- [实验设计](实验设计.md)
- [文本实验报告：计入解码](实验报告_含解码.md)
- [文本实验报告：不计解码](实验报告_不计解码.md)
- `images/`：上述报告实际引用的 image-15.png、9 张计入解码图、9 张不计解码图。
- `code/`：当前已找到的文本五算法公共测量代码、Rust 数值后端与视频 FFmpeg 测量入口，与文本/视频子目录的内核一致；没有把报告生成脚本当作实验实现。

## 缺失的原始实验代码/环境材料

| 未找到的文件 | 报告中的依据 | 影响 |
|---|---|---|
| seven-codec-comparison.py | 实验设计第 4 节中的 03_compression_evaluation/03_compression_evaluation/code/seven-codec-comparison.py | 缺少含 LZ4、ZSTD-3 的七算法统一实现；现有五算法代码不能完整复现对应文本报告 |
| Dockerfile / 原 Docker 镜像构建配置 | 设计要求固定 Python、PyArrow、Rust codec、FFmpeg 版本，但没有附实际构建文件 | 无法确认原镜像的完整依赖和构建步骤 |
| Docker 资源档位启动脚本（如 .sh/.ps1） | 报告列有 cpuset、cpu-quota、memory 参数；本地未找到实际执行脚本 | 缺少原始批量运行、失败状态记录和各档位调度入口 |

以上在当前工作区、原始实验留档和已有历史归档中未找到；并非本次整理时移走。需要补找原文件或镜像配置。本次没有新增替代实现，没有重跑 Docker，也不把软件 CPU 时间配额当作真实树莓派硬件。

## 现有公共代码的使用范围

文本代码可测 Gzip、Gorilla、Chimp、Parquet+ZSTD、Parquet+Snappy；视频代码可实际转码和完整解码。它们可在配置好的容器内作为测量内核使用，但不包含上述缺失的七算法/容器编排逻辑。原始数据统一读取 ocean/data，新输出应指定 ocean/runs 下的独立目录，避免覆盖旧结果。

原稿中的资源档位、失败状态及含/不含解码两种口径均保留在报告中，没有为了配合现有代码而修改数值。没有独立生图、生表或报告生成脚本。
