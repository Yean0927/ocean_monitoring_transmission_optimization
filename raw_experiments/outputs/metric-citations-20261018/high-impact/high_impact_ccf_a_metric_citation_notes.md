# OceanFlex：优先 CCF A 类的指标引用方案

核对日期：2026-10-18。本版替换上一版的文献编号与导入文件；未改动论文源文件。范围仅限指标选择，不再为“压缩—传输—解压”时延分解另配引文。

## 推荐六篇

六篇的出版物均列入 CCF A 类：SIGCOMM、SOSP、IEEE Transactions on Visualization and Computer Graphics（TVCG）、IEEE Transactions on Networking（原 IEEE/ACM Transactions on Networking）。已查阅 [CCF 2026 目录原文镜像](https://scdm-shu.github.io/ccf/2026-CCF-Ranking.pdf)，相应 PDF 页码为 13、27、44、10（均从封面起计，1-based）。CCF 官网直连本次遇到访问校验，未声称成功读取官网正文。

被引次数统一使用 Crossref REST API 的 `is-referenced-by-count`，按下列 DOI 于 2026-10-18 实时查询。它是该 DOI 记录的 Crossref 被引计数，不是 Google Scholar 总被引，也不是年度被引率或严格他引数；未将同论文的期刊、会议或预印本记录相加。Semantic Scholar 和 OpenAlex 本次均返回 HTTP 429，未采用未经核验的更高数值。

| 新编号 | 文献 | 级别 | Crossref 被引次数 | 指标对应 |
|---|---|---|---:|---|
| [1] | Alizadeh, M., Greenberg, A., Maltz, D. A., Padhye, J., Patel, P., Prabhakar, B., Sengupta, S. & Sridharan, M. **Data Center TCP (DCTCP)**. SIGCOMM 2010, 63–74. [DOI](https://doi.org/10.1145/1851182.1851192) | CCF A 会议 | 1285 | transmission throughput and latency |
| [2] | Lindstrom, P. **Fixed-Rate Compressed Floating-Point Arrays**. IEEE Transactions on Visualization and Computer Graphics 20(12), 2674–2683 (2014). [DOI](https://doi.org/10.1109/TVCG.2014.2346458) | CCF A 期刊 | 651 | compression ratio and processing overhead |
| [3] | Balasubramanian, A., Levine, B. N. & Venkataramani, A. **DTN Routing as a Resource Allocation Problem**. SIGCOMM 2007, 373–384. [DOI](https://doi.org/10.1145/1282380.1282422) | CCF A 会议 | 359 | delivery reliability under intermittent connectivity |
| [4] | Floyd, S. & Jacobson, V. **Random Early Detection Gateways for Congestion Avoidance**. IEEE/ACM Transactions on Networking 1(4), 397–413 (1993). [DOI](https://doi.org/10.1109/90.251892) | CCF A 期刊 | 4538 | buffer occupancy |
| [5] | Zaharia, M., Das, T., Li, H., Hunter, T., Shenker, S. & Stoica, I. **Discretized Streams: Fault-Tolerant Streaming Computation at Scale**. SOSP 2013, 423–438. [DOI](https://doi.org/10.1145/2517349.2522737) | CCF A 会议 | 771 | recovery behavior |
| [6] | Fall, K. **A Delay-Tolerant Network Architecture for Challenged Internets**. SIGCOMM 2003, 27–34. [DOI](https://doi.org/10.1145/863955.863960) | CCF A 会议 | 1019 | disruptions、buffer limitations 与 data loss 的动机 |

原 [6] Knutsson & Björkman (1999) 在同一 Crossref 口径下为 16 次；新 [6] 为 1019 次。新 [6] 放在数据丢失句后，不能沿用为原来时延分解句的引文。

## 全文核对：为何能支撑这些指标

### [1] DCTCP：吞吐量与时延

[作者单位全文](https://www.microsoft.com/en-us/research/wp-content/uploads/2017/01/dctcp-sigcomm2010.pdf) 的 §4.1 直接测量吞吐量和队列长度，Fig. 14 展示吞吐量；§4.2.2、Fig. 21 比较小流请求完成时延。SIGCOMM 官方还将其列为 [2021 Test of Time Award](https://www.sigcomm.org/awards/acm-sigcomm-test-of-time-paper-award) 获奖论文。

适用边界：对象为数据中心网络。可支撑同时评价吞吐量与时延的必要性，不等于海上链路的完整时延定义，也不直接规定是否纳入编解码时间。

### [2] ZFP：压缩比与处理开销

[正式版全文](https://vis.cs.ucdavis.edu/vis2014papers/TVCG/papers/2674_20tvcg12-lindstrom-2346458.pdf) 的 Table 1 报告压缩比；§5.2、Fig. 6 同时报告压缩和解压吞吐量，Fig. 7 报告缓存与总执行时间。作者单位 [LLNL 项目页](https://computing.llnl.gov/projects/zfp) 可交叉核对题名、作者、年份、页码和 DOI。

适用边界：原始工作研究有损浮点数组压缩。此处引用压缩收益和计算成本应同时评价这一方法先例，不声称其数据格式、压缩算法或质量要求与 OceanFlex 相同。若只讨论无损传感数值，可改用 FPC（IEEE Transactions on Computers，2009，CCF A；DOI 10.1109/TC.2008.131；本次 Crossref 218 次），其 §5.1–5.3 更直接覆盖无损压缩比、编解码吞吐量及内存消耗。

### [3] RAPID：间歇连接下的交付可靠性

[论文全文](https://web.cs.ucla.edu/classes/cs217/2007SIGCOMM_DTNRouting.pdf) 的 §6 明确以平均时延、最大时延和错过截止时间为评价目标；Figs. 9、11、15 等报告截止时间内交付比例，Fig. 15 考察有限缓存对交付的影响。论文在 40 辆公交车组成的 DTN 中部署原型，并结合真实轨迹仿真。

适用边界：交付可靠性在该工作中具体体现为截止时间内交付比例，不能把这个定义默认为 OceanFlex 的最终交付率。OceanFlex 应自行写明截止时间、是否去重以及记录/字节口径。

### [4] RED：缓存/队列占用

[作者全文](https://www.icir.org/floyd/papers/early.twocolumn.pdf) 的摘要与算法直接以平均队列长度反映拥塞；Fig. 5 比较平均队列长度与吞吐量。它说明仅测吞吐量不足以描述缓存积压和时延代价。

适用边界：研究对象为网关队列。OceanFlex 的应用层持久缓存与路由器队列是不同层次；可引用其评价动机，不能直接移植阈值、队列模型或参数。

### [5] D-Streams：恢复过程

[作者全文](https://people.eecs.berkeley.edu/~matei/papers/2013/sosp_spark_streaming.pdf) 的 §6.2、Figs. 10–12 记录故障前后处理时间与恢复过程，比较故障数量、检查点周期和并行规模的影响。

适用边界：节点故障后的流处理恢复，不等于海上链路重连。用作恢复动态评价先例，OceanFlex 仍需定义重连后首次交付、恢复正常性能、积压消退等不同事件。

### [6] Fall：断连、有限缓存与数据丢失

[SIGCOMM 正式版全文](https://www.cl.cam.ac.uk/~ey204/teaching/ACS/R212_2013_2014/papers/fall_sigcomm_2003.pdf) 的 §2.1 讨论断连与长时间排队；§2.3 讨论受限存储；§4.9 讨论接触机会迟迟不出现时的数据积压，以及缓存满时拒收消息、过期清理与丢弃策略。

适用边界：这是架构与机制依据，不是直接建立 data loss 统计标准的实证论文。它支持说明为何要观测断连和缓存受限造成的数据未交付/丢弃。永久丢失、超期丢弃和仍待补传应在本文中区分；不得把有损压缩误差当作传输丢失。

## 建议替换段落

> We evaluate OceanFlex from an end-to-end perspective using transmission throughput and latency [1], compression ratio and processing overhead [2], and delivery reliability under intermittent connectivity [3]. We further examine buffer occupancy [4] and recovery behavior [5], and report data loss to assess the consequences of disruptions and buffer limitations [6].

本段引用的是指标选择及评价动机，不表示以上论文在同一场景下共同采用了一套统一标准。按用户要求，此处省去上一版最后那句时延分解表述。

LaTeX 版本：

```latex
We evaluate OceanFlex from an end-to-end perspective using transmission
throughput and latency~\cite{alizadeh2010dctcp}, compression ratio and
processing overhead~\cite{lindstrom2014fixedrate}, and delivery reliability
under intermittent connectivity~\cite{balasubramanian2007dtn}.
We further examine buffer occupancy~\cite{floyd1993red} and recovery
behavior~\cite{zaharia2013discretized}, and report data loss to assess the
consequences of disruptions and buffer limitations~\cite{fall2003dtn}.
```

## 文件

- `OceanFlex_high_impact_references.ris`：以上六条，供 EndNote/Zotero 使用。
- `citation_counts.tsv`：同一口径的被引次数，注明日期和 DOI。
- `selected_reference_metadata.json`：六篇的原始 Crossref 元数据与选择说明。
- `crossref_candidates.json`、`red_crossref.json`：候选核验原始记录。未对不同版本被引计数求和。

说明：官方 CCF 端点返回的 HTML 为访问校验页，旁存的 `ccf_*.html` 不用作等级证据。等级证据为上文所链接的 CCF 2026 原文 PDF。
