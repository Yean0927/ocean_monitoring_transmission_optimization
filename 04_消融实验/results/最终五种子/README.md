# 最终 RTO/容量修复版：五种子系统消融

本目录为正式结果入口，包含随机种子 31、32、33、34、35 的全部八组结果，共 40 次已完成运行；实验窗口 3600 s，排空期 0 s，等待缓存容量 50 MB。

- [正式实验报告](../../reports/系统消融_最终RTO修复版_五种子报告.md)
- [总体均值与样本标准差](five-seed-aggregate.csv)
- [逐种子总体指标，40 行](per-seed-summary.csv)
- [D1–D4、V1、I1 分流统计，48 行](by-stream-five-seed-aggregate.csv)
- [文本/视频/图像送达率，24 行](data-type-success-five-seed.csv)
- seed-31/ 至 seed-35/：各含八组逐文件 CSV、协议决策轨迹、metrics JSON、运行日志、summary.csv、by-stream.csv 和单种子 report.md。
- provenance.json：原实验执行时的来源和二进制哈希，历史绝对路径按原样保留；当前包内对应位置见 package-provenance.json。
- package-provenance.json、trace-audit.json：本次归集映射、载荷/源码校验和 40 次运行的逐文件审计。

最终 FULL 为 98.34% 送达、0% 拒收/淘汰、1.66% 截止待完成；受限平均送达时间 387.78 ± 0.60 s。早期 repeated-five-seeds-20261015 中 FULL 67.04% 的矩阵已由本目录的完整修复版替代，不得混入本次均值。

复现与重新汇总命令见 [系统实验代码说明](../../system_20260928/README.md)。本次收录未重跑 3600 s 矩阵；已核对 40 次原始轨迹，重新计算的统计与原最终汇总一致。
