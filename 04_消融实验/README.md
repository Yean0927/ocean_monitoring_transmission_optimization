# 第四阶段：特征消融与系统消融

最终入口是 `xgboost_features/` 与 [system_20260928/](system_20260928/README.md)。系统实验已补齐最终 RTO/容量修复版的五个随机种子（31–35）、八组消融，共 40 次运行的原始结果与复现代码。

- [报告与历史说明](reports/README.md)
- [最终五种子结果](results/最终五种子/README.md)：总体/分类汇总、seed-31 至 seed-35 原始轨迹、决策、metrics、日志与 provenance。
- [系统实验与代码说明](system_20260928/README.md)：实验设置、指标、已测量输入、最终运行库和五种子执行/校验命令。
- `figures/`：消融对照、五种子送达率、分类型结果和源速率表。

最终系统为 FULL、WO_PROTOCOL、WO_COMPRESSION、WO_CACHE、BASELINE、ADD_PROTOCOL、ADD_COMPRESSION、ADD_CACHE 八组，种子 31–35。最终 QUIC 源码直接收录于 third_party/quic，勿重复应用旧补丁。对应的历史最终可执行文件和 QUIC 动态库已收录于 system_20260928/runtime，运行入口默认显式加载该独立修复库。

在 ocean 根目录运行：

```sh
python 04_消融实验/xgboost_features/run.py verify
python 04_消融实验/xgboost_features/run.py ablate
python 04_消融实验/system_20260928/run_five_seeds.py --verify-only
python 04_消融实验/system_20260928/run_five_seeds.py --output runs/系统消融五种子_新运行 --workers 2
```

保存的 prepared 输入可直接重放；重新压缩测量的命令和跨机器编译要求见系统实验 README。XGBoost 特征消融必须对每个变体重新训练，默认 anchor_id 分组。系统缓存粒度是文件，第三阶段是 packet/chunk；指标区分成功、拒收/淘汰和截止待完成。若 FULL 预测始终选择同一协议，不能单据此证明动态切换收益。

图表版本：figures/消融对比 的总体均值对应最终修复版；figures/五种子送达率 对应早期未完成全部修复的矩阵，不能与最终报告混用。最终三类数据结果见 results/最终五种子/data-type-success-five-seed.csv。
