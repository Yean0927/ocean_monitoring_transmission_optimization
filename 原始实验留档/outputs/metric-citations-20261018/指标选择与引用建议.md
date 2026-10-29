# OceanFlex 指标选择与引用建议

检索与核对日期：2026-10-18。依据用户截图中的评价段落整理；未改动论文源文件。

## 使用原则

以下文献能说明各项指标在相关研究中已有使用先例，并解释为什么适合本系统。它们不共同构成一套覆盖八项指标的统一标准。建议按传输性能、压缩效率、可靠性与恢复三类分配引文。

## 六篇建议文献与证据

| 编号 | 参考文献 | 对应指标与证据位置 | 核对范围与使用边界 |
|---|---|---|---|
| [1] | Zhang, B., Jin, X., Ratnasamy, S., Wawrzynek, J. & Lee, E. A. **AWStream: Adaptive Wide-Area Streaming Analytics**. SIGCOMM 2018, 236–252. DOI: [10.1145/3230543.3230554](https://doi.org/10.1145/3230543.3230554) | 吞吐量、时延、变化带宽下的适应过程。§5.3，尤其 Fig. 11 展示吞吐量、时延和准确率随时间变化。 | 已核对[作者全文](https://awstream.github.io/paper/awstream.pdf)。应用为广域流分析，可支撑评价维度；不据此声称其采用 OceanFlex 相同的有效吞吐量定义。 |
| [2] | Blalock, D., Madden, S. & Guttag, J. **Sprintz: Time Series Compression for the Internet of Things**. Proceedings of the ACM on Interactive, Mobile, Wearable and Ubiquitous Technologies 2(3), Article 93, 1–23 (2018). DOI: [10.1145/3264903](https://doi.org/10.1145/3264903) | 压缩比、压缩速度、解压速度。§5.3–5.5，Figs. 2–5。 | 已核对[作者全文](https://arxiv.org/html/1808.02515)。适合传感时序压缩的先例。该论文的速度评价不等于网络端到端时延，也不直接替代 CPU 利用率测量。 |
| [3] | Qin, S., Feng, G., Qin, W., Ge, Y. & Pathmasuntharam, J. S. **Performance Evaluation of Data Transmission in Maritime Delay-Tolerant-Networks**. IEICE Transactions on Communications E96.B(6), 1435–1443 (2013). DOI: [10.1587/transcom.E96.B.1435](https://doi.org/10.1587/transcom.E96.B.1435) | 海上数据交付率。摘要明确分析航道船舶向岸上基站的数据交付率，并以实际船舶轨迹驱动仿真验证。 | 已核对[出版社摘要与书目信息](https://www.jstage.jst.go.jp/article/transcom/E96.B/6/E96.B_1435/_article/-char/en)。未取得并逐页核对全文，不补造图号；不将其扩展为支撑压缩或恢复指标。 |
| [4] | Abbas, A., Shah, B., Al-Obeidat, F. & Iqbal, F. **Bounded message delay with threshold time constraint in delay tolerant networks (DTNs)**. 2016 3rd MEC International Conference on Big Data and Smart City (ICBDSC), 1–6 (2016). DOI: [10.1109/ICBDSC.2016.7460368](https://doi.org/10.1109/ICBDSC.2016.7460368) | 缓存占用、交付率、交付时延。作者机构摘要明确列出 delivery delay、delivery ratio、buffer occupancy (usage)。 | 已核对[作者机构记录中的摘要](https://zu.elsevierpure.com/en/publications/bounded-message-delay-with-threshold-time-constraint-in-delay-tol-5/)及 Crossref 元数据；未逐页核对全文，不能补充精确计算公式或图号。 |
| [5] | Zaharia, M., Das, T., Li, H., Hunter, T., Shenker, S. & Stoica, I. **Discretized Streams: Fault-Tolerant Streaming Computation at Scale**. SOSP 2013, 423–438. DOI: [10.1145/2517349.2522737](https://doi.org/10.1145/2517349.2522737) | 恢复时间、故障期间性能及恢复到稳定状态的过程。§6.2，Figs. 10–12；Fig. 10 记录故障前、故障时与故障后分段处理时间。 | 已核对[作者全文](https://people.eecs.berkeley.edu/~matei/papers/2013/sosp_spark_streaming.pdf)。它讨论集群流处理故障；可作为恢复评价的方法先例，不能将节点状态恢复时间等同于海上链路恢复时间，也不声称其直接使用 OceanFlex 的数据丢失量指标。 |
| [6] | Knutsson, B. & Björkman, M. **Adaptive end-to-end compression for variable-bandwidth communication**. Computer Networks 31(7), 767–779 (1999). DOI: [10.1016/S0169-7552(98)00299-2](https://doi.org/10.1016/S0169-7552(98)00299-2) | 压缩与解压计算开销、吞吐量和时延之间的权衡。出版社提供的“End-to-end compression”节片段明确讨论发送前压缩、接收后解压的计算—通信权衡。 | 已核对[出版社摘要与章节片段](https://www.sciencedirect.com/science/article/abs/pii/S0169755298002992)及 Crossref 元数据。用于解释端到端评价边界；不称其提出了 OceanFlex 所采用的完整时延公式。 |

## 指标如何选择和定义

下表是结合 OceanFlex 任务提出的测量建议；不是声称每篇文献均采用这些定义。采用前需与已有代码、图表和实际计时点一致。

| 指标 | 建议口径 | 在论文中的作用 |
|---|---|---|
| 有效吞吐量（goodput） | 接收端成功获得、去重后的应用有效数据量 / 明确的统计时长。压缩比较时另注明按压缩前等效字节还是线上字节计算；稳态时长与包含断连的全程时长分开说明。 | 核心传输性能，参考 [1] 的评价维度。不要把 goodput 与含重传、协议头的线速吞吐混用。 |
| 端到端时延 | 明确源端起点、岸端终点。若从生成/采集开始，应覆盖组批、排队和断连等待；若仅从压缩开始，不包括此前等待，需据实说明。建议报告中位数与 P95。 | 核心传输性能，参考 [1,6] 的评价动机。跨设备单向计时需交代时钟同步或校准办法。 |
| 压缩比 | 例如 CR = 原始字节数 / 压缩后字节数，数值越大越好。若用空间节省率，单独写为 1 − 压缩后字节数 / 原始字节数。 | 核心压缩效率，参考 [2]；不要混用互为倒数或差值的口径。 |
| 处理开销 | 优先明确为压缩/编码时间、解压/解码时间，或每 MB 处理时间；若实际测量 CPU、内存，再单独报告。 | 解释压缩收益是否被计算开销抵消，参考 [2,6]。 |
| 交付率 | 在预先定义的截止时间内，唯一成功交付的记录数 / 同一输入集合的应交付记录数。按记录或按字节计算需要明确。 | 核心可靠性，海上场景依据 [3]，缓存受限依据 [4]。 |
| 数据丢失量 | 明确是溢出丢弃、过期丢弃、不可恢复损坏，还是截至截止时间尚未收到的数据。区分仍待补传的积压与已确认不可恢复的丢弃。 | 建议作为本文场景补充指标，而非声称以上六篇直接共同确立其标准地位。若它只是与交付率同一口径的互补量，可放辅助结果。 |
| 缓存占用 | B(t) 的时序曲线，注明字节或记录数，以及压缩前/后存储口径；补充峰值或峰值/容量。 | 机制解释，参考 [4]；展示断连期间积压增长及恢复后消退。 |
| 恢复行为 | 将链路重连后至首次成功交付的时间、至稳定性能的时间、至积压消退的时间分开。若持续有新数据，定义恢复至正常基线范围而非要求缓存严格为零。 | 参考 [5] 的故障前后动态评价方法；这些具体事件边界由本文定义。 |

建议主结果保留有效吞吐量、端到端时延、交付率；压缩实验单独报告压缩比及编解码开销；断连实验以缓存曲线和恢复时间解释机制，数据丢失量补充说明可靠性边界。这是本次对任务的建议，不是文献规定的优先级。

如果存在有损压缩，需另外报告适合数据类型的重建质量或任务准确率。这里的传输数据丢失与压缩失真属于不同问题。[1] 同时报告时延与任务准确率，可作为同时考察效率和质量的先例。

## 可替换原段落的英文草稿

以下保留截图已有评价范围，未假定实际测量了新的 CPU、内存或恢复时间指标。方括号编号对应上表；LaTeX 可替换为同目录 BibTeX 文件中的 citation key。

> We evaluate OceanFlex from an end-to-end perspective. The evaluation covers transmission throughput and latency [1], compression ratio and processing overhead [2], and delivery reliability under intermittent connectivity [3]. We further examine buffer occupancy [4] and recovery behavior [5], and report data loss to assess the consequences of disruptions and buffer limitations. For compression experiments, end-to-end latency includes edge-side compression, network transmission, and shore-side decompression or decoding, accounting for both computation and communication costs [6].

若实际已量化恢复时间，可把 recovery behavior 改为 recovery time，并在实验设置中定义起止事件。若吞吐量实际统计的是应用有效负载，可把 transmission throughput 改为 application goodput。若时延还包含组批/队列等待，需在英文计时范围中相应补充，避免把它们隐藏在 network transmission 中。

## 检索和元数据记录

- 路由：nature-academic-search / multi-source-search。会话未提供 academic-search MCP 工具。
- 技能 OpenAlex 回退脚本最初因系统 Python 版本过低无法执行；改用 Python 3.12 后，OpenAlex 返回 HTTP 429。其结果未被用来编造检索条目。
- 随后通过公开网络检索定位作者全文、出版社页面和作者机构记录，依据 DOI 去重，优先正式发表版本；上述六条 DOI 均在 Crossref API 成功核验。
- `crossref_metadata.json` 保存六条接口元数据。AWStream、Sprintz、Discretized Streams 的题名与副标题在 Crossref 分开存储，导出时已合并为作者全文中的完整题名。Sprintz 的 Article 93 据作者全文补全。
- 部分候选文献未被选入：仅有间接相关性、与另一条覆盖重复，或不能直接支撑目标指标。
- 未统计或宣称引用量、系统检索覆盖率、统一行业标准地位。

## 导入文件

- `OceanFlex_metric_references.ris`：6 条，适用于 Zotero、EndNote 等。

引用键依次为 `zhang2018awstream`、`blalock2018sprintz`、`qin2013maritime`、`abbas2016bounded`、`zaharia2013discretized`、`knutsson1999adaptive`。
