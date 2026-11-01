# CDN 论文截图：第 4586 页中英对照



**Original:** Our contributions are summarized as follows:

**中文:** 我们的贡献概括如下：

<a id="S003"></a>


**Original:** We conduct a motivating case study illustrating that different applications prioritize different resource types when selecting CDN servers. Our goal is to handle delay-sensitive, bandwidth-sensitive, and CPU-sensitive CDN requests with an integrated solution.

**中文:** 我们开展了一项研究动机案例分析，说明不同应用在选择 CDN 服务器时，对不同类型资源的优先级有所不同。我们的目标是通过一套集成方案，处理时延敏感型、带宽敏感型和 CPU 敏感型 CDN 请求。

<a id="S004"></a>


**Original:** We propose Polygon, a QUIC-powered CDN server selection system that supports multiple resource demands. Polygon leverages QUIC’s advantages to eliminate the extra delays and overhead introduced by the dispatcher.

**中文:** 我们提出 Polygon，一种基于 QUIC、支持多种资源需求的 CDN 服务器选择系统。Polygon 利用 QUIC 的优势，消除调度器引入的额外时延和开销。

<a id="S005"></a>


**Original:** Real-world experiments and extensive simulations demonstrate Polygon’s ability to reduce job completion time, improve resource utilization, and efficiently reschedule global resources with a moderate overhead.

**中文:** 真实环境实验和大量仿真表明，Polygon 能够缩短任务完成时间、提高资源利用率，并以适度的开销高效地重新调度全局资源。

<a id="S006"></a>

**Source:** p.4586 S006

**Original:** A preliminary version of this paper has been published in [16]. The new contributions include design enhancements, implementation optimizations, comprehensive evaluations in real-world and simulation environments, and an in-depth discussion of Polygon’s scalability and future research directions. In Section III, we improve Polygon’s design on network resource measurements, server allocation algorithms, and resource weight vector calculations, making its operation more effective and efficient. Real-world deployment and extensive evaluations in various scenarios, presented in Section IV and Section V respectively, demonstrate the feasibility of deploying Polygon in production environments. Designed to be a resource-efficient CDN server selection system, Polygon can provide benefits including 1) less job completion time, 2) higher resource utilization, 3) fewer error requests, and 4) the capability to reschedule global resources dynamically.

**中文:** 本文的初步版本已发表于文献 [16]。本版本新增的贡献包括设计改进、实现优化、在真实环境和仿真环境中的全面评估，以及对 Polygon 可扩展性和未来研究方向的深入讨论。在第 III 节中，我们从网络资源测量、服务器分配算法和资源权重向量计算三个方面改进 Polygon 的设计，使其运行更加有效、高效。第 IV 节和第 V 节分别介绍真实环境部署及多种场景下的广泛评估，验证了在生产环境中部署 Polygon 的可行性。作为一种高效利用资源的 CDN 服务器选择系统，Polygon 能够带来以下益处：1）缩短任务完成时间；2）提高资源利用率；3）减少出错请求；4）实现全局资源的动态重新调度。

<a id="S007"></a>

**Source:** p.4586 S007

**Original:** The following of this paper is organized as below. Section II introduces the insights that inspired Polygon. Section III describes the system design and implementation. A real-world evaluation is presented in Section IV, followed by extensive evaluations under various situations in Section V. Subsequently, Section VI discusses the scalability of Polygon and explores some future research. Section VII enumerates the related work. Finally, we conclude our work in Section VIII.

**中文:** 本文其余部分安排如下。第 II 节介绍启发 Polygon 设计的研究洞见。第 III 节描述系统设计与实现。第 IV 节介绍真实环境评估，第 V 节进一步给出多种情形下的广泛评估。随后，第 VI 节讨论 Polygon 的可扩展性，并探讨未来研究方向。第 VII 节介绍相关工作。最后，第 VIII 节总结全文。

<a id="S008"></a>

**Source:** p.4586 S008

**Original:** II. MOTIVATING CASE STUDY

**中文:** II. 研究动机案例分析

<a id="S009"></a>

**Source:** p.4586 S009

**Original:** CDNs have evolved to support various content types, including web content [17], video streaming [18], and replica databases [19]. This section presents a case study revealing that CDN requests for different content types rely on distinct resource demands.

**中文:** CDN 已发展为能够支持多种内容类型，包括网页内容 [17]、视频流 [18] 和副本数据库 [19]。本节通过案例分析揭示：不同内容类型的 CDN 请求具有不同的资源需求。

<a id="S010"></a>

**Source:** p.4586 S010

**Original:** A. Three CDN Request Patterns

**中文:** A. 三种 CDN 请求模式

<a id="S011"></a>

**Source:** p.4586 S011

**Original:** We select three typical websites, Twitter.com, YouTube.com, and Microsoftonline.com, as case studies. These sites serve millions of users globally [20] and rely heavily on global CDN infrastructure [21], representing online microblogging, streaming media, and productivity tools, respectively.

**中文:** 我们选择三个典型网站——Twitter.com、YouTube.com 和 Microsoftonline.com——作为案例分析对象。这些网站为全球数百万用户提供服务 [20]，并高度依赖全球 CDN 基础设施 [21]，分别代表在线微博、流媒体和生产力工具三类应用。

<a id="S012"></a>

**Source:** p.4586 S012

**Original:** We analyze the waiting time and download time [22], [23] of CDN requests on these three websites. According to Chrome’s document [24], waiting time is defined as the duration from sending a request to receiving the first byte of the response, comprising one RTT and the server execution time. A longer waiting time indicates a longer server execution time given the same RTT delay. Download time is the duration spent receiving data, with a longer download time suggesting a slower network or larger data volume. These two parts constitute the majority of time to complete CDN requests [23]. We use Chrome-HAR¹ to capture the waiting time and download time, and treat each website entry as a CDN request. The capture process for these websites is conducted on the same machine under the same network conditions.

**中文:** 我们分析这三个网站中 CDN 请求的等待时间和下载时间 [22], [23]。根据 Chrome 文档 [24]，等待时间定义为从发送请求到收到响应的第一个字节所经过的时间，由一次往返时间（RTT）和服务器执行时间组成。在 RTT 时延相同的情况下，等待时间越长，表明服务器执行时间越长。下载时间是接收数据所用的时间；下载时间越长，通常意味着网络越慢或数据量越大。这两个部分占据了 CDN 请求完成时间的大部分 [23]。我们使用 Chrome-HAR¹ 记录等待时间和下载时间，并将每个网站条目视为一个 CDN 请求。对这些网站的数据采集均在同一台机器、相同网络条件下进行。

<a id="S013"></a>

**Source:** p.4586 S013

**Original:** We calculate the ratios of waiting time and download time for each request. The Cumulative Distribution Functions (CDF) of these ratios for the three websites are shown in Fig. 1. Notably, over 60% of requests on Microsoftonline.com have a waiting time ratio exceeding 0.8, while Twitter.com and YouTube.com have fewer requests with such high waiting time ratios. In contrast, the download time ratios for requests on Microsoftonline.com are smaller than those on Twitter.com and YouTube.com.

**中文:** 我们计算每个请求的等待时间占比和下载时间占比。图 1 展示了三个网站中这些占比的累积分布函数（CDF）。值得注意的是，Microsoftonline.com 中超过 60% 的请求，其等待时间占比超过 0.8；而 Twitter.com 和 YouTube.com 中具有如此高等待时间占比的请求较少。相比之下，Microsoftonline.com 请求的下载时间占比低于 Twitter.com 和 YouTube.com。

<a id="C001"></a>

**Source:** p.4586 C001

**Original:** Fig. 1. Cumulative distribution functions of the ratios of waiting time and download time. (a) Ratio of waiting time. (b) Ratio of download time.

**中文:** 图 1. 等待时间占比和下载时间占比的累积分布函数。（a）等待时间占比；（b）下载时间占比。

<a id="F001"></a>

![图 1](assets/fig1.png)

图中纵轴 CDF：累积分布函数；横轴分别为等待时间占比和下载时间占比。网站名称保留原文。

<a id="S014"></a>

**Source:** p.4586 S014

**Original:** These differences in waiting time and download time highlight that different services rely on distinct network resources. We introduce the concept of resource sensitivity: the degree to which request complete time changes due to variations in resource quality. Considering classic application scenarios, we categorize CDN requests into three sensitivity-related groups based on three common resource types: delay, bandwidth, and CPU capability. These resource types are widely recognized as representative of service resources [26].

**中文:** 等待时间和下载时间的这些差异表明，不同服务依赖不同的网络资源。我们引入“资源敏感性”这一概念：资源质量发生变化时，请求完成时间随之变化的程度。结合典型应用场景，我们根据三种常见资源类型——时延、带宽和 CPU 能力——将 CDN 请求划分为三类与敏感性相关的请求。这些资源类型被广泛认为具有服务资源的代表性 [26]。

<a id="T001"></a>

**Source:** p.4586 T001

**Original:** TABLE I. RESOURCE CONFIGURATIONS IN THE CASE STUDY

**中文:** 表 I. 案例分析中的资源配置

![表 I 原图](assets/table1.png)

| Service resource / 服务资源 | Service quality / 服务质量 | Delay / 时延 | Bandwidth / 带宽 | CPU |
|---|---|---|---|---|

| Delay / 时延 | Poor / 差 | 131 ms | 248 Mbps | 1 vCPU |

| Delay / 时延 | Medium / 中等 | 112 ms | 248 Mbps | 1 vCPU |

| Delay / 时延 | Good / 好 | 96 ms | 248 Mbps | 1 vCPU |

| Bandwidth / 带宽 | Poor / 差 | 34 ms | 3 Mbps | 1 vCPU |

| Bandwidth / 带宽 | Medium / 中等 | 34 ms | 248 Mbps | 1 vCPU |

| Bandwidth / 带宽 | Good / 好 | 34 ms | 758 Mbps | 1 vCPU |

| CPU / CPU | Poor / 差 | 27 ms | 917 Mbps | 1 shared vCPU / 1 个共享 vCPU |

| CPU / CPU | Medium / 中等 | 27 ms | 917 Mbps | 1 vCPU |

| CPU / CPU | Good / 好 | 27 ms | 917 Mbps | 4 vCPU |

<a id="S015"></a>

**Source:** p.4586 S015

**Original:** ¹ Chrome-HAR [25] is a file format that records session data of the browsing pages, including each entry’s timestamps, load time, and size.

**中文:** ¹ Chrome-HAR [25] 是一种记录网页浏览会话数据的文件格式，包括每个条目的时间戳、加载时间和大小。


## 术语对照

| 原文 | 本页译法 |
|---|---|

| CDN | 内容分发网络 |

| Polygon | Polygon（系统名称，保留原文） |

| QUIC | QUIC（协议名称，保留原文） |

| dispatcher | 调度器 |

| waiting time | 等待时间 |

| download time | 下载时间 |

| RTT | 往返时间 |

| CDF | 累积分布函数 |

| resource sensitivity | 资源敏感性 |

| job completion time | 任务完成时间 |

| vCPU | 虚拟 CPU |


## 阅读提示

本节通过比较不同网站请求的等待时间占比与下载时间占比，引出“资源敏感性”概念。案例分析在原论文后续页继续，本截图未提供后续内容。
