# 实验报告总索引

更新日期：2026-10-26。文件压缩按文本/视频/弱CPU Docker，缓存阶段按容量/优先级及共用链路状态整理。各实验目录包含实际代码、报告和既有图片，不包含独立生图、生表脚本。

## 01_自适应协议选择

| 报告/说明 | 原始来源 |
|---|---|
| [figures/model_performance_comparison/figure_notes.md](01_adaptive_protocol_selection/figures/model_performance_comparison/figure_notes.md) | `/Users/yean/program/海洋监测/outputs/method-comparison-8x6/figure_notes.md` |
| [reports/xgboost_training_summary.md](01_adaptive_protocol_selection/reports/xgboost_training_summary.md) | `/Users/yean/program/海洋监测/ocean/01_adaptive_protocol_selection/sample_results/model_results/xgboost_export/training-summary.md` |
| [reports/adaptive_protocol_selection_report.md](01_adaptive_protocol_selection/reports/adaptive_protocol_selection_report.md) | `/Users/yean/program/海洋监测/ocean/01_adaptive_protocol_selection/README-source.md` |
| [reports/training_data_notes.md](01_adaptive_protocol_selection/reports/training_data_notes.md) | `/Users/yean/program/海洋监测/ocean/01_adaptive_protocol_selection/sample_results/training_data/dataset-summary.md` |

## 02_文件压缩

| 报告/说明 | 原始来源 |
|---|---|
| [weak_cpu_docker/experiment_report_without_decode.md](02_file_compression/weak_cpu_docker/experiment_report_without_decode.md) | `/Users/yean/program/海洋监测/ocean/02_file_compression/edge-text-compression-experiment-report.md` |
| [weak_cpu_docker/experiment_report_with_decode.md](02_file_compression/weak_cpu_docker/experiment_report_with_decode.md) | `/Users/yean/program/海洋监测/ocean/raw_experiments/experiment_reports/weak_cpu_with_decode.md` |
| [weak_cpu_docker/experiment_design.md](02_file_compression/weak_cpu_docker/experiment_design.md) | `/Users/yean/program/海洋监测/ocean/02_file_compression/edge-compression-feasibility-docker-experiment-design.md` |
| [text_compression/experiment_report.md](02_file_compression/text_compression/experiment_report.md) | `/Users/yean/program/海洋监测/ocean/02_file_compression/text_compression_report.md` |
| [text_compression/experiment_design_and_optimization.md](02_file_compression/text_compression/experiment_design_and_optimization.md) | `/Users/yean/program/海洋监测/ocean/02_file_compression/text_compression实验.md` |
| [video_compression/experiment_report.md](02_file_compression/video_compression/experiment_report.md) | `/Users/yean/Downloads/video_compression.md`（2026-10-26 用户提供最新版） |
| [weak_cpu_docker/video_compression_report.md](02_file_compression/weak_cpu_docker/video_compression_report.md) | 同上，Docker 弱 CPU 视频章节原文摘录 |
| [video_compression/video_file8_remeasurement_report.md](02_file_compression/video_compression/video_file8_remeasurement_report.md) | `/Users/yean/program/海洋监测/outputs/video-file8-recomputed-20261018/README.md` |

## 03_缓存机制

| 报告/说明 | 原始来源 |
|---|---|
| [priority_experiments/original_experiment_design.md](03_cache_mechanism/priority_experiments/original_experiment_design.md) | `/Users/yean/program/海洋监测/ocean/03_cache_mechanism/third-stage-cache-mechanism-report.md` |
| [priority_experiments/experiment_report.md](03_cache_mechanism/priority_experiments/experiment_report.md) | `/Users/yean/program/海洋监测/cache_exam/packet-level-cache-priority-experiment-report.md` |
| [priority_experiments/mechanism_and_discrete_simulation_report.md](03_cache_mechanism/priority_experiments/mechanism_and_discrete_simulation_report.md) | `/Users/yean/program/海洋监测/cache_exam/cache-priority-mechanism-experiment-report.md` |
| [cache_capacity_experiments/experiment_report.md](03_cache_mechanism/cache_capacity_experiments/experiment_report.md) | `/Users/yean/program/海洋监测/cache_exam/fifo-cache-capacity-scan/fifo-cache-capacity-scan.md` |
| [link_conditions/README.md](03_cache_mechanism/link_conditions/README.md) | `/Users/yean/program/海洋监测/实验代码归档/20261026_缓存阶段重整前/03_缓存机制/dynamic-link-config/README.md` |

## 04_消融实验

最终系统实验入口：[代码与复现说明](04_ablation_experiments/system_20260928/README.md)、[40 次运行结果](04_ablation_experiments/results/final_five_seeds/README.md)。当前正式结果采用 RTO/发送容量修复版种子 31–35；早期五种子图表单独保留版本说明。

| 报告/说明 | 原始来源 |
|---|---|
| [figures/five_seed_delivery_rates/delivery_rates.md](04_ablation_experiments/figures/five_seed_delivery_rates/delivery_rates.md) | `/Users/yean/program/海洋监测/outputs/delivery-ratio-five-seeds-20261015/delivery_rates.md` |
| [figures/five_seed_delivery_rates/qa_notes.md](04_ablation_experiments/figures/five_seed_delivery_rates/qa_notes.md) | `/Users/yean/program/海洋监测/outputs/delivery-ratio-five-seeds-20261015/qa_notes.md` |
| [figures/ablation_comparison/compact_reordered_notes.md](04_ablation_experiments/figures/ablation_comparison/compact_reordered_notes.md) | `/Users/yean/program/海洋监测/outputs/ablation-line-comparison-8x6/compact_reordered_notes.md` |
| [figures/ablation_comparison/dual_axis_reordered_notes.md](04_ablation_experiments/figures/ablation_comparison/dual_axis_reordered_notes.md) | `/Users/yean/program/海洋监测/outputs/ablation-line-comparison-8x6/dual_axis_reordered_notes.md` |
| [figures/ablation_comparison/figure_notes.md](04_ablation_experiments/figures/ablation_comparison/figure_notes.md) | `/Users/yean/program/海洋监测/outputs/ablation-line-comparison-8x6/figure_notes.md` |
| [figures/source_generation_rates/source_generation_rates.md](04_ablation_experiments/figures/source_generation_rates/source_generation_rates.md) | `/Users/yean/program/海洋监测/outputs/source-generation-rate-table-20261019/source_generation_rates.md` |
| [figures/matched_size_figures/README.md](04_ablation_experiments/figures/matched_size_figures/README.md) | `/Users/yean/program/海洋监测/outputs/matched-8x6-figures/README.md` |
| [figures/delivery_rate_comparison/combined_figure_notes.md](04_ablation_experiments/figures/delivery_rate_comparison/combined_figure_notes.md) | `/Users/yean/program/海洋监测/outputs/delivery-ratio-two-figures/combined_figure_notes.md` |
| [figures/delivery_rate_comparison/figure_notes.md](04_ablation_experiments/figures/delivery_rate_comparison/figure_notes.md) | `/Users/yean/program/海洋监测/outputs/delivery-ratio-two-figures/figure_notes.md` |
| [figures/delivery_rate_comparison/single_8x6_notes.md](04_ablation_experiments/figures/delivery_rate_comparison/single_8x6_notes.md) | `/Users/yean/program/海洋监测/outputs/delivery-ratio-two-figures/single_8x6_notes.md` |
| [figures/delivery_rate_comparison/solid_style_notes.md](04_ablation_experiments/figures/delivery_rate_comparison/solid_style_notes.md) | `/Users/yean/program/海洋监测/outputs/delivery-ratio-two-figures/solid_style_notes.md` |
| [reports/xgboost_feature_ablation.md](04_ablation_experiments/reports/xgboost_feature_ablation.md) | `/Users/yean/program/海洋监测/ocean/04_ablation_experiments/xgboost_features/README.md` |
| [reports/historical_versions/README.md](04_ablation_experiments/reports/historical_versions/README.md) | `/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/06_ablation_reports/README.md` |
| [reports/historical_versions/abandoned-stall-before-periodic-probe_report.md](04_ablation_experiments/reports/historical_versions/abandoned-stall-before-periodic-probe_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/abandoned-stall-before-periodic-probe/report.md` |
| [reports/historical_versions/current-ablation-report.md](04_ablation_experiments/reports/historical_versions/current-ablation-report.md) | `/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/06_ablation_reports/current-ablation-report.md` |
| [reports/historical_versions/integrated-ablation-report.md](04_ablation_experiments/reports/historical_versions/integrated-ablation-report.md) | `/Users/yean/program/海洋监测/cache_exam/ns3-simulation-main/06_ablation_reports/integrated-ablation-report.md` |
| [reports/historical_versions/prior-3900s-eight-groups_report.md](04_ablation_experiments/reports/historical_versions/prior-3900s-eight-groups_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/prior-3900s-eight-groups/report.md` |
| [reports/historical_versions/prior-five-before-additive_report.md](04_ablation_experiments/reports/historical_versions/prior-five-before-additive_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/prior-five-before-additive/report.md` |
| [reports/historical_versions/prior-recovery-full-stalled-results_report.md](04_ablation_experiments/reports/historical_versions/prior-recovery-full-stalled-results_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/prior-recovery-full-stalled-results/report.md` |
| [reports/historical_versions/repeated-five-seeds-20261015_overall-metrics-table.md](04_ablation_experiments/reports/historical_versions/repeated-five-seeds-20261015_overall-metrics-table.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/repeated-five-seeds-20261015/overall-metrics-table.md` |
| [reports/historical_versions/repeated-five-seeds-20261015_repeat-summary.md](04_ablation_experiments/reports/historical_versions/repeated-five-seeds-20261015_repeat-summary.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/repeated-five-seeds-20261015/repeat-summary.md` |
| [reports/historical_versions/stall-validation-seeds-32-34-20261015_report.md](04_ablation_experiments/reports/historical_versions/stall-validation-seeds-32-34-20261015_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/stall-validation-seeds-32-34-20261015/report.md` |
| [reports/historical_versions/system_ablation_20260924_five_variants_report.md](04_ablation_experiments/reports/historical_versions/system_ablation_20260924_five_variants_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260924/results/report.md` |
| [reports/system_ablation_original_eight_variants_single_seed_report.md](04_ablation_experiments/reports/system_ablation_original_eight_variants_single_seed_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/results/report.md` |
| [reports/system_ablation_final_rto_fixed_five_seeds_report.md](04_ablation_experiments/reports/system_ablation_final_rto_fixed_five_seeds_report.md) | `/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/validation/repeated-five-seeds-rto-fixed-20261015/five-seed-report.md` |

## 05_Case_Study

| 报告/说明 | 原始来源 |
|---|---|
| [reports/20261016_audit_report.md](05_Case_Study/reports/20261016_audit_report.md) | `/Users/yean/program/海洋监测/outputs/marine-data-case-study/audit-20261016/report.md` |
| [reports/case_study.md](05_Case_Study/reports/case_study.md) | `/Users/yean/program/海洋监测/outputs/marine-data-case-study/case_study.md` |
| [reports/evidence_notes.md](05_Case_Study/reports/evidence_notes.md) | `/Users/yean/program/海洋监测/outputs/marine-data-case-study/evidence_notes.md` |
| [reports/figure_notes.md](05_Case_Study/reports/figure_notes.md) | `/Users/yean/program/海洋监测/outputs/marine-data-case-study/figure_notes.md` |
| [reports/historical_versions/case_study.md](05_Case_Study/reports/historical_versions/case_study.md) | `/Users/yean/program/海洋监测/ocean/04_ablation_experiments/resource_case_study/case_study.md` |
| [reports/historical_versions/evidence_notes.md](05_Case_Study/reports/historical_versions/evidence_notes.md) | `/Users/yean/program/海洋监测/ocean/04_ablation_experiments/resource_case_study/evidence_notes.md` |
| [reports/historical_versions/figure_notes.md](05_Case_Study/reports/historical_versions/figure_notes.md) | `/Users/yean/program/海洋监测/ocean/04_ablation_experiments/resource_case_study/figure_notes.md` |

## 文稿与参考材料

| 报告/说明 | 原始来源 |
|---|---|
| [cdn-page-4586-translation/paper.md](manuscript_and_reference_materials/cdn-page-4586-translation/paper.md) | `/Users/yean/program/海洋监测/outputs/cdn-page-4586-translation/paper.md` |
| [cdn-page-4586-translation/translation_notes.md](manuscript_and_reference_materials/cdn-page-4586-translation/translation_notes.md) | `/Users/yean/program/海洋监测/outputs/cdn-page-4586-translation/translation_notes.md` |
| [metric-citations-20261018/high-impact/high_impact_ccf_a_metric_citation_notes.md](manuscript_and_reference_materials/metric-citations-20261018/high-impact/high_impact_ccf_a_metric_citation_notes.md) | `/Users/yean/program/海洋监测/outputs/metric-citations-20261018/high-impact/high_impact_ccf_a_metric_citation_notes.md` |
| [metric-citations-20261018/metric_selection_and_citation_notes.md](manuscript_and_reference_materials/metric-citations-20261018/metric_selection_and_citation_notes.md) | `/Users/yean/program/海洋监测/outputs/metric-citations-20261018/metric_selection_and_citation_notes.md` |

## PDF 实验报告与参考材料

- [02_file_compression/video_compression/video_frame_compression_report.pdf](02_file_compression/video_compression/video_frame_compression_report.pdf)
- [manuscript_and_reference_materials/ocean_monitoring_data_transfer_optimization_requirements.pdf](manuscript_and_reference_materials/ocean_monitoring_data_transfer_optimization_requirements.pdf)

## Word 阅读版

- [文本压缩实验报告 WPS 阅读版](02_file_compression/text_compression/experiment_report_wps.docx)：由同目录 Markdown 转换，包含 9 张内嵌原图。
