# 系统消融：最终修复版五种子实验

更新日期：2026-10-26。本目录提供最终 RTO/发送容量修复版的实际实验代码、已测量的 prepared 输入，以及原运行对应的可执行文件和独立 QUIC 库。最终结果为种子 31–35、8 组 × 5 次，共 40 次；早期 repeated-five-seeds-20261015 的不稳定矩阵属于历史结果。

## 实验设置

- 四节点 N0—N1—N2—N3：传感器源端、边缘组装/缓存节点、中间转发节点、岸端接收节点；N1—N2 为瓶颈。
- TCP CUBIC、TCP BBR 和外部 SIGNET QUIC BBR 均在 ns-3.42 中运行。最终 QUIC 已包含兼容性、可靠性扩展、指数退避、发送缓冲容量及 RTO 恢复判定修复，源码见 ../../third_party/quic；不是未经修改的标准 QUIC。
- H = 3600 s，排空期 0 s；有缓存组使用 50,000,000 B 文件等待队列、Priority-MaxF、非抢占服务。组装区和传输协议缓冲不计入该等待队列。
- 六类目标总源速率依次为 D1 0.000050665、D2 0.000028665、D3 0.0512、D4 0.0000694、V1 1.667848、I1 0.413944 Mbps。文本按真实记录字节长度控制到达；视频按 208,481 B/s，图片为中位大小 258,715 B、每 5 s 一张；设备数为参考设置，各类合并为一路。
- 文本最长组装等待 D1–D4 为 120、300、1、1800 s；同时受原样本文件大小上限约束。视频和图像收齐一个完整对象再压缩。
- 压缩产物由实际代码生成并校验，prepared 保留对应实测压缩/解压缩时间。N1 校验组装原文，N3 校验传输载荷，并按该对象处理时间回放解压缩。不是用报告平均压缩比替代数据。
- 模型预先为每个文件、每个链路状态生成预测，仿真按发送时刻读取对应状态结果；不是在线测量网络后再次调用模型。组间使用相同源事件与链路轨迹；种子控制链路随机丢包。

## 八组定义

| 组别 | 协议选择 | 压缩 | 文件等待队列 |
|:--|:--|:--|:--|
| FULL | XGBoost | 开启 | Priority-MaxF |
| WO_PROTOCOL | TCP CUBIC | 开启 | Priority-MaxF |
| WO_COMPRESSION | XGBoost，原始文件特征 | 关闭 | Priority-MaxF |
| WO_CACHE | XGBoost | 开启 | 关闭，忙时拒收 |
| BASELINE | TCP CUBIC | 关闭 | 关闭，忙时拒收 |
| ADD_PROTOCOL | XGBoost，原始文件特征 | 关闭 | 关闭，忙时拒收 |
| ADD_COMPRESSION | TCP CUBIC | 开启 | 关闭，忙时拒收 |
| ADD_CACHE | TCP CUBIC | 关闭 | Priority-MaxF |

## 文件与结果

- system-ablation.cc：与最终运行 provenance 的源码 SHA256 一致。
- prepare.py：真实文件压缩、源事件与模型预测准备；引用本包第二阶段压缩内核和 xgboost_features/model。
- prepared/：最终 40 次运行共用输入。只把 files.json/files.tsv 的载荷路径改为相对 assets/，模型路径指向本包；事件、载荷内容、处理耗时和模型预测未改变。run_experiment.py 以 prepared 为子进程工作目录。
- runtime/：从最终修复构建留档中原样复制的 macOS arm64 程序和独立 QUIC 库；不重新链接。源码、QUIC 库和最终补丁与历史 provenance 匹配，但当前留档程序哈希与历史记录不一致，原因尚未确认；双值与检查结论见 package-provenance.json。运行入口通过 DYLD_LIBRARY_PATH 优先加载 runtime/lib，并从 OCEAN_NS3_ROOT/build/lib 加载其余 ns-3 依赖。
- run_experiment.py：执行单个种子的八组，支持 --seed、--variants、--binary、--quic-lib-dir、--skip-summary。
- run_five_seeds.py：运行五种子、校验已有轨迹、重新汇总总体及分类型结果。
- audit_results.py：核对源事件字节、时间顺序、协议预测、summary 与原始轨迹一致性、缓存容量及日志。超过 600 s 的传输项单列诊断；只有显式 --fail-on-stall 才以此判失败。
- [最终结果目录](../results/最终五种子/README.md) 与 [正式报告](../reports/系统消融_最终RTO修复版_五种子报告.md)。

## 复现命令

在 ocean 根目录执行。校验已归档的 40 次运行，不重新仿真：

```sh
python3 04_消融实验/system_20260928/run_five_seeds.py --verify-only
```

使用保存的精确输入重新运行全部种子；输出目录必须为空，以防覆盖已有实验：

```sh
export OCEAN_NS3_ROOT="$PWD/原始实验留档/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42"
python3 04_消融实验/system_20260928/run_five_seeds.py --output runs/系统消融五种子_新运行 --workers 2
```

完成后自动生成每种子报告、五种子总体均值/样本标准差和三类数据送达率。文本先合并 D1–D4 的成功字节与生成字节再相除。

单种子与仅汇总：

```sh
python3 04_消融实验/system_20260928/run_experiment.py --seed 31 --output runs/系统消融单种子/seed-31
python3 04_消融实验/system_20260928/run_five_seeds.py --aggregate-only --results runs/系统消融五种子_新运行
```

重新测量压缩耗时、生成全新负载时，使用新 prepared 目录并安装 requirements.txt 及支持相应编码器的 FFmpeg；新的实测处理耗时可能不同，不能混入已保存的五种子统计：

```sh
python3 04_消融实验/system_20260928/prepare.py --duration 3600 --drain 0 --cache-bytes 50000000 --text-waits 120,300,1,1800 --image-period 5 --image-quality 75 --video-bytes-per-second 208481 --output runs/系统消融新输入
python3 04_消融实验/system_20260928/run_five_seeds.py --prepared runs/系统消融新输入 --output runs/系统消融新输入五种子 --workers 2
```

跨平台需在 ns-3.42 中使用本包 third_party/quic 重新编译模块及本目录 C++，并用 --binary 指定对应程序。随附 runtime 只适用于当前 macOS arm64 工具链，仍依赖其余 ns-3 动态库；不是跨平台独立安装包。旧 quic-ns3.42.patch 与最终 candidate-rto-capacity.patch 均保留作来源记录，不应再次应用到已修复源码。

## 指标口径与边界

G 为源端实际生成原始字节；D 为 H 前完成完整文件接收、校验和解压缩的原始等价字节；L 为应用层拒收/淘汰字节；P = G − D − L。三项比例均除以 G；物理包丢失但仍可重传的数据不直接计入 L。受限平均送达时间按原始字节加权，成功项为完成时间减首字节生成时间，未送达项为 H 减首字节生成时间。各种子先独立计算，再取算术均值和样本标准差。

D1/D3 Parquet 和 D4 Chimp 沿用字段/观测语义口径，图像/视频为有损压缩；不声称所有原始文本均能字节级恢复。FULL 本次模型选择始终为 QUIC BBR，结果不能单独证明在线协议切换的收益。
