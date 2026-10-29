# 开发校验目录

此目录保留短时校验和弃用运行。不要将这里的数值作为正式实验结果。

- abandoned-ack-gated-run：额外应用确认导致停滞的早期实现。
- abandoned-flow-control-run：接收缓冲与流量控制错误导致 QUIC 连接提前终止；该目录五组表格已作废。
- loss-reordering：重叠重传的短时真实载荷验证。
- window-corrected：窗口初步修正后仍检测到双向额度混用。
- window-ranges：对重叠字节去重、区分双向额度后进行大视频验证。

最终五组结果必须位于上级 results/，通过载荷校验、事件顺序和字节守恒检查，并且日志不得含 QUIC_ABORT。
- abandoned-incomplete-run：早期 QUIC 重传缓存污染与发送窗口停滞，含无缓存组载荷不一致；不得用于结果比较。
- frame-boundary：单流帧封包后无缓存组 900 s 字节校验通过。
- rto-oldest：单流帧封包与受限 RTO 修复后，完整组 1500 s 交付 17 段视频，结束无在服务文件。
- abandoned-before-gap-probe：接收端缺口请求加入之前的完整五组尝试，存在长期未完成及载荷错误；全部作废。
- gap-probe-full 与 gap-probe-nocache：加入缺口请求后的 3600+300 s 完整校验；两组原样复制到最终 `results/`。
- final-five-gap-probe.log：同一二进制完成其余三组并生成最终五组汇总的运行日志。
