# 真实模型定向重跑复核

2026-11-04，deepseek-flash，3/3通过，耗时356.641秒。[原始报告](REPORT.md)、[原始summary](summary.json)、[逐项账本核查及文件摘要](review.json)。复核来自AI读取实际Trace及SQLite快照，不等于独立人工签字。

| 场景 | 实际路径与费用 | 原始证据 |
|---|---|---|
| resume | 首段检索4、两次生成失败各1，tool_failed且保留素材，已花6。续跑重新开库，复用原素材，premium脚本7、保存1；总14≤预算15，完成10:45≤截止11:30 | [input](resume/input.json)、[first](resume/first_run.json)、[resumed](resume/result.json)、[snapshot](resume/database_snapshot.json) |
| save_failure_resume | 首段检索4、脚本7成功；保存两次失败均0费用，明确tool_failed、无方案。续跑只补保存1，总12，素材/脚本ID和内容不变，失败尝试保留 | [input](save_failure_resume/input.json)、[first](save_failure_resume/first_run.json)、[resumed](save_failure_resume/result.json)、[snapshot](save_failure_resume/database_snapshot.json) |
| no_assets | premium检索NO_ASSETS花4，再估lean并检索仍NO_ASSETS花2，结束needs_materials，总6；未生成脚本或保存方案 | [input](no_assets/input.json)、[result](no_assets/result.json)、[snapshot](no_assets/database_snapshot.json) |

三组实际账本合计、依赖、模拟时间、预算、成功步骤无重复收费、保存回执及跨调用结果保留均核对通过。原始summary的real_model_decision_quality_verified默认待审标记保持false；复核另存，不篡改自动报告。

模型短解释存在误差：resume续跑第2步在估算前写预计11–13，实际工具估算是14；后续调用和保存均按14执行。模型选择premium在预算内合法，但不是最低费用方案。no_assets两档检索花6，比离线策略的一次检索4多；通过不等于最优。保留原始依据和费用。

本轮每组从新的评估数据库开始；resume和save_failure_resume内部的首段与续跑共享各自数据库并重新连接。本轮费用不与首轮live目录的独立案例相加，也不构成对首轮已中断数据库的原地恢复证明。生产实际同任务续跑须使用原request_id和原数据库。

首轮10/13与本轮3/3对应同一运行源码；累计13类场景有通过证据，不等于一次全量13/13或统计可靠性。[两轮证据汇总](../LIVE-REVIEW.md)。业务工具、素材、脚本模板、费用和时间均为合成模拟，模拟预算不含真实API收费。
