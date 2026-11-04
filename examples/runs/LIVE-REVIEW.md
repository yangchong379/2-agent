# 真实模型两轮证据汇总

首轮10/13，三个受到MODEL_TRANSPORT_FAILED影响的场景定向重跑3/3。两轮运行源码一致，累计13类场景均有通过证据；不是一次全量13/13，也不代表稳定成功率。没有为重跑修改运行逻辑。

[首轮原始报告](live/REPORT.md) · [首轮复核及失败](live/REVIEW.md) · [重跑原始报告](live-retry/REPORT.md) · [重跑复核](live-retry/REVIEW.md) · [机器可读对应表](live-comparison.json)

| 场景 | 首轮 | 定向重跑 | 选用实际输出及Trace |
|---|---|---|---|
| normal | PASS | 未重跑 | [completed](live/normal/result.json) |
| missing_budget | PASS | 未重跑 | [needs_info](live/missing_budget/result.json) |
| missing_deadline | PASS | 未重跑 | [needs_info](live/missing_deadline/result.json) |
| budget_replan | PASS | 未重跑 | [completed](live/budget_replan/result.json) |
| deadline_replan | PASS | 未重跑 | [completed](live/deadline_replan/result.json) |
| tool_failure_replan | PASS | 未重跑 | [completed](live/tool_failure_replan/result.json) |
| persistent_failure | PASS | 未重跑 | [tool_failed](live/persistent_failure/result.json) |
| no_feasible | PASS | 未重跑 | [constraints_infeasible](live/no_feasible/result.json) |
| duplicate | PASS | 未重跑 | [completed](live/duplicate/result.json) |
| resume | FAIL | PASS | [completed](live-retry/resume/result.json) |
| save_failure_resume | FAIL | PASS | [completed](live-retry/save_failure_resume/result.json) |
| no_assets | FAIL | PASS | [needs_materials](live-retry/no_assets/result.json) |
| step_limit | PASS | 未重跑 | [incomplete_step_limit](live/step_limit/result.json) |

每个案例目录保存input.json、dataset.json、result.json（内含Trace）和database_snapshot.json；续跑案例另有first_run.json。首轮失败不删除、不改成通过。原始JSON摘要由各轮review.json记录。

真实决策有预算12超10后改8、生成失败后保留素材转轻量方案、保存失败后结束并在续跑仅补保存、无素材换档检索后请求补资料等不同路径。成功或未完成状态依据工具与数据库事实。

业务工具、素材、脚本、费用和耗时均为合成模拟；真正调用远端模型选择工具及参数。模拟时钟不计网络等待，费用不含真实API账单。复核由AI完成，短解释的已知误差和费用非最优问题见各轮REVIEW；不隐去这些限制。
