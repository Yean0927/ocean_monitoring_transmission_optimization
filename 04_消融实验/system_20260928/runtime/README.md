# 原最终运行程序

system-ablation-rto-fixed 和 lib/libns3.42-quic-optimized.dylib 原样收录自最终独立修复构建的留档。原执行记录见 ../../results/最终五种子/provenance.json；当前文件哈希见 package-provenance.json。

源码、QUIC 库和最终补丁均与原记录匹配。可执行文件当前哈希为 457ba7600968eded598fc41e6a03f7144351c811a545d8c12315fccc8d4c39c4，原 provenance 记录为 604f5dd4ba4fe725d1c8243ad5b7392c6ad95fcebdba13713b1aa3f9d5e02f7b，原因尚未确认。这里与当前留档程序逐字节一致，但不能声称已找回与历史哈希完全一致的二进制。本次没有覆盖原 provenance。

程序适用于原 macOS arm64 环境，仍依赖 OCEAN_NS3_ROOT/build/lib 中的其余 ns-3.42 动态库。run_experiment.py 以 DYLD_LIBRARY_PATH 优先指定本目录 lib，避免加载旧公共 QUIC 库。本次 30 s 冒烟已检查动态加载记录，确认加载此库并完成 34 个文件送达。

跨机器/平台请使用 ocean/third_party/quic 和 ../system-ablation.cc 重新编译，通过 --binary 和 --quic-lib-dir 指定新构建；不修改这里的历史程序后继续沿用原二进制哈希。
