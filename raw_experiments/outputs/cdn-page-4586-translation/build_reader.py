from pathlib import Path
from PIL import Image
import json
root=Path('/Users/yean/program/海洋监测/outputs/cdn-page-4586-translation')
source=Path('/var/folders/_k/tgt_g54s3z533ynv0gmb6ykw0000gn/T/codex-clipboard-69c8fdba-f33f-40f6-895f-6123c698547f.png')
im=Image.open(source)
w,h=im.size
# Coordinates refer to the supplied 1178 × 1566 screenshot.
for name,box in [('fig1.png',(610,70,1110,258)),('table1.png',(618,392,1100,605))]:
    scaled=tuple(round(v*(w/1178 if i%2==0 else h/1566)) for i,v in enumerate(box))
    im.crop(scaled).save(root/'assets'/name)
blocks=[
('S001','paragraph','that Polygon can more efficiently reschedule global resources compared with the commercial CDN schemes.','（承接上一页）与商业 CDN 方案相比，Polygon 能够更高效地重新调度全局资源。'),
('S002','paragraph','Our contributions are summarized as follows:','我们的贡献概括如下：'),
('S003','list-item','We conduct a motivating case study illustrating that different applications prioritize different resource types when selecting CDN servers. Our goal is to handle delay-sensitive, bandwidth-sensitive, and CPU-sensitive CDN requests with an integrated solution.','我们开展了一项研究动机案例分析，说明不同应用在选择 CDN 服务器时，对不同类型资源的优先级有所不同。我们的目标是通过一套集成方案，处理时延敏感型、带宽敏感型和 CPU 敏感型 CDN 请求。'),
('S004','list-item','We propose Polygon, a QUIC-powered CDN server selection system that supports multiple resource demands. Polygon leverages QUIC’s advantages to eliminate the extra delays and overhead introduced by the dispatcher.','我们提出 Polygon，一种基于 QUIC、支持多种资源需求的 CDN 服务器选择系统。Polygon 利用 QUIC 的优势，消除调度器引入的额外时延和开销。'),
('S005','list-item','Real-world experiments and extensive simulations demonstrate Polygon’s ability to reduce job completion time, improve resource utilization, and efficiently reschedule global resources with a moderate overhead.','真实环境实验和大量仿真表明，Polygon 能够缩短任务完成时间、提高资源利用率，并以适度的开销高效地重新调度全局资源。'),
('S006','paragraph','A preliminary version of this paper has been published in [16]. The new contributions include design enhancements, implementation optimizations, comprehensive evaluations in real-world and simulation environments, and an in-depth discussion of Polygon’s scalability and future research directions. In Section III, we improve Polygon’s design on network resource measurements, server allocation algorithms, and resource weight vector calculations, making its operation more effective and efficient. Real-world deployment and extensive evaluations in various scenarios, presented in Section IV and Section V respectively, demonstrate the feasibility of deploying Polygon in production environments. Designed to be a resource-efficient CDN server selection system, Polygon can provide benefits including 1) less job completion time, 2) higher resource utilization, 3) fewer error requests, and 4) the capability to reschedule global resources dynamically.','本文的初步版本已发表于文献 [16]。本版本新增的贡献包括设计改进、实现优化、在真实环境和仿真环境中的全面评估，以及对 Polygon 可扩展性和未来研究方向的深入讨论。在第 III 节中，我们从网络资源测量、服务器分配算法和资源权重向量计算三个方面改进 Polygon 的设计，使其运行更加有效、高效。第 IV 节和第 V 节分别介绍真实环境部署及多种场景下的广泛评估，验证了在生产环境中部署 Polygon 的可行性。作为一种高效利用资源的 CDN 服务器选择系统，Polygon 能够带来以下益处：1）缩短任务完成时间；2）提高资源利用率；3）减少出错请求；4）实现全局资源的动态重新调度。'),
('S007','paragraph','The following of this paper is organized as below. Section II introduces the insights that inspired Polygon. Section III describes the system design and implementation. A real-world evaluation is presented in Section IV, followed by extensive evaluations under various situations in Section V. Subsequently, Section VI discusses the scalability of Polygon and explores some future research. Section VII enumerates the related work. Finally, we conclude our work in Section VIII.','本文其余部分安排如下。第 II 节介绍启发 Polygon 设计的研究洞见。第 III 节描述系统设计与实现。第 IV 节介绍真实环境评估，第 V 节进一步给出多种情形下的广泛评估。随后，第 VI 节讨论 Polygon 的可扩展性，并探讨未来研究方向。第 VII 节介绍相关工作。最后，第 VIII 节总结全文。'),
('S008','heading','II. MOTIVATING CASE STUDY','II. 研究动机案例分析'),
('S009','paragraph','CDNs have evolved to support various content types, including web content [17], video streaming [18], and replica databases [19]. This section presents a case study revealing that CDN requests for different content types rely on distinct resource demands.','CDN 已发展为能够支持多种内容类型，包括网页内容 [17]、视频流 [18] 和副本数据库 [19]。本节通过案例分析揭示：不同内容类型的 CDN 请求具有不同的资源需求。'),
('S010','heading','A. Three CDN Request Patterns','A. 三种 CDN 请求模式'),
('S011','paragraph','We select three typical websites, Twitter.com, YouTube.com, and Microsoftonline.com, as case studies. These sites serve millions of users globally [20] and rely heavily on global CDN infrastructure [21], representing online microblogging, streaming media, and productivity tools, respectively.','我们选择三个典型网站——Twitter.com、YouTube.com 和 Microsoftonline.com——作为案例分析对象。这些网站为全球数百万用户提供服务 [20]，并高度依赖全球 CDN 基础设施 [21]，分别代表在线微博、流媒体和生产力工具三类应用。'),
('S012','paragraph','We analyze the waiting time and download time [22], [23] of CDN requests on these three websites. According to Chrome’s document [24], waiting time is defined as the duration from sending a request to receiving the first byte of the response, comprising one RTT and the server execution time. A longer waiting time indicates a longer server execution time given the same RTT delay. Download time is the duration spent receiving data, with a longer download time suggesting a slower network or larger data volume. These two parts constitute the majority of time to complete CDN requests [23]. We use Chrome-HAR¹ to capture the waiting time and download time, and treat each website entry as a CDN request. The capture process for these websites is conducted on the same machine under the same network conditions.','我们分析这三个网站中 CDN 请求的等待时间和下载时间 [22], [23]。根据 Chrome 文档 [24]，等待时间定义为从发送请求到收到响应的第一个字节所经过的时间，由一次往返时间（RTT）和服务器执行时间组成。在 RTT 时延相同的情况下，等待时间越长，表明服务器执行时间越长。下载时间是接收数据所用的时间；下载时间越长，通常意味着网络越慢或数据量越大。这两个部分占据了 CDN 请求完成时间的大部分 [23]。我们使用 Chrome-HAR¹ 记录等待时间和下载时间，并将每个网站条目视为一个 CDN 请求。对这些网站的数据采集均在同一台机器、相同网络条件下进行。'),
('S013','paragraph','We calculate the ratios of waiting time and download time for each request. The Cumulative Distribution Functions (CDF) of these ratios for the three websites are shown in Fig. 1. Notably, over 60% of requests on Microsoftonline.com have a waiting time ratio exceeding 0.8, while Twitter.com and YouTube.com have fewer requests with such high waiting time ratios. In contrast, the download time ratios for requests on Microsoftonline.com are smaller than those on Twitter.com and YouTube.com.','我们计算每个请求的等待时间占比和下载时间占比。图 1 展示了三个网站中这些占比的累积分布函数（CDF）。值得注意的是，Microsoftonline.com 中超过 60% 的请求，其等待时间占比超过 0.8；而 Twitter.com 和 YouTube.com 中具有如此高等待时间占比的请求较少。相比之下，Microsoftonline.com 请求的下载时间占比低于 Twitter.com 和 YouTube.com。'),
('C001','caption','Fig. 1. Cumulative distribution functions of the ratios of waiting time and download time. (a) Ratio of waiting time. (b) Ratio of download time.','图 1. 等待时间占比和下载时间占比的累积分布函数。（a）等待时间占比；（b）下载时间占比。'),
('S014','paragraph','These differences in waiting time and download time highlight that different services rely on distinct network resources. We introduce the concept of resource sensitivity: the degree to which request complete time changes due to variations in resource quality. Considering classic application scenarios, we categorize CDN requests into three sensitivity-related groups based on three common resource types: delay, bandwidth, and CPU capability. These resource types are widely recognized as representative of service resources [26].','等待时间和下载时间的这些差异表明，不同服务依赖不同的网络资源。我们引入“资源敏感性”这一概念：资源质量发生变化时，请求完成时间随之变化的程度。结合典型应用场景，我们根据三种常见资源类型——时延、带宽和 CPU 能力——将 CDN 请求划分为三类与敏感性相关的请求。这些资源类型被广泛认为具有服务资源的代表性 [26]。'),
('T001','table','TABLE I. RESOURCE CONFIGURATIONS IN THE CASE STUDY','表 I. 案例分析中的资源配置'),
('S015','footnote','¹ Chrome-HAR [25] is a file format that records session data of the browsing pages, including each entry’s timestamps, load time, and size.','¹ Chrome-HAR [25] 是一种记录网页浏览会话数据的文件格式，包括每个条目的时间戳、加载时间和大小。')]
rows=[['Delay','Poor','131 ms','248 Mbps','1 vCPU'],['Delay','Medium','112 ms','248 Mbps','1 vCPU'],['Delay','Good','96 ms','248 Mbps','1 vCPU'],['Bandwidth','Poor','34 ms','3 Mbps','1 vCPU'],['Bandwidth','Medium','34 ms','248 Mbps','1 vCPU'],['Bandwidth','Good','34 ms','758 Mbps','1 vCPU'],['CPU','Poor','27 ms','917 Mbps','1 shared vCPU'],['CPU','Medium','27 ms','917 Mbps','1 vCPU'],['CPU','Good','27 ms','917 Mbps','4 vCPU']]
glossary=[{'original':a,'translation':b} for a,b in [('CDN','内容分发网络'),('Polygon','Polygon（系统名称，保留原文）'),('QUIC','QUIC（协议名称，保留原文）'),('dispatcher','调度器'),('waiting time','等待时间'),('download time','下载时间'),('RTT','往返时间'),('CDF','累积分布函数'),('resource sensitivity','资源敏感性'),('job completion time','任务完成时间'),('vCPU','虚拟 CPU')]]
md=['# CDN 论文截图：第 4586 页中英对照\n','来源：用户提供的单页截图。页眉：IEEE/ACM Transactions on Networking，Vol. 32，No. 6，December 2024。论文标题及作者未出现在本页。仅翻译截图可见内容；页首句子承接上一页。\n','阅读顺序：引言续文 → II. 研究动机案例分析 → A. 三种 CDN 请求模式 → 图 1 → 表 I → 脚注。\n']
source_blocks=[]
for index,(id,kind,en,zh) in enumerate(blocks,1):
    md.append(f'<a id="{id}"></a>\n\n**Source:** p.4586 {id}\n\n**Original:** {en}\n\n**中文:** {zh}\n')
    entry={'id':id,'page':4586,'type':kind,'original':en,'translation':zh,'reading_order':index,'confidence':'high','source_image':str(source)}
    if id=='C001':
        md.append('<a id="F001"></a>\n\n![图 1](assets/fig1.png)\n\n图中纵轴 CDF：累积分布函数；横轴分别为等待时间占比和下载时间占比。网站名称保留原文。\n')
        source_blocks.append({'id':'F001','page':4586,'type':'figure','asset':'assets/fig1.png','caption_id':'C001','placed_near':'S013','confidence':'high'})
    if id=='T001':
        md.append('![表 I 原图](assets/table1.png)\n\n| Service resource / 服务资源 | Service quality / 服务质量 | Delay / 时延 | Bandwidth / 带宽 | CPU |\n|---|---|---|---|---|\n')
        mapping={'Delay':'时延','Bandwidth':'带宽','CPU':'CPU','Poor':'差','Medium':'中等','Good':'好','1 shared vCPU':'1 个共享 vCPU'}
        for row in rows:
            md.append('| '+' | '.join(f'{v} / {mapping[v]}' if v in mapping else v for v in row)+' |\n')
        entry['asset']='assets/table1.png'
        entry['rows']=rows
    source_blocks.append(entry)
md.append('\n## 术语对照\n\n| 原文 | 本页译法 |\n|---|---|\n')
for g in glossary: md.append(f"| {g['original']} | {g['translation']} |\n")
md.append('\n## 阅读提示\n\n本节通过比较不同网站请求的等待时间占比与下载时间占比，引出“资源敏感性”概念。案例分析在原论文后续页继续，本截图未提供后续内容。\n')
(root/'paper.md').write_text('\n'.join(md),encoding='utf-8')
(root/'source_map.json').write_text(json.dumps({'source':str(source),'scope':'single supplied screenshot, printed page 4586','source_format':'scanned-image','blocks':source_blocks,'glossary':glossary},ensure_ascii=False,indent=2),encoding='utf-8')
(root/'translation_notes.md').write_text('''# 翻译说明

- 仅处理用户提供的第 4586 页截图，不推测整篇论文的标题、作者或缺失内容。
- 页首是上一页句子的结尾，译文明确标注“承接上一页”。
- 输入是 PNG 页面截图，参照 scanned-pdf 图像型来源流程处理；逐块直接视觉转录并核对，无显示公式。
- “Motivating Case Study”采用“研究动机案例分析”，表示用于引出系统设计动机的案例分析。
- 图表的数值、单位、网站名称和参考文献编号保持原文；表格中“1 shared vCPU”译为“1 个共享 vCPU”。
- 截图未明确写出时间占比的分母，因此译文保留“等待时间占比”“下载时间占比”，不自行补充公式。
- 图 1 和表 I 从截图中裁切，保留在 assets/ 中；表 I 同时转录为可编辑表格。
- 页面页眉记录在元数据中；页脚授权下载声明不属于论文正文，未纳入正文翻译。
- 当前文件是完整覆盖所给单页的译稿，非整篇论文译稿；完整论文其余页未提供。
''',encoding='utf-8')
print(root/'paper.md')
