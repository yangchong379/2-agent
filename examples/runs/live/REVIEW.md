# 真实模型运行复核

模型：deepseek-flash；真实评估10/13业务断言通过，耗时888.984秒。

[原始自动报告](REPORT.md) · [原始summary](summary.json) · [逐项账本/状态核查及文件摘要](review.json)

业务工具、素材、脚本模板、费用和耗时为本地合成模拟；模型选择工具、参数和后续动作来自真实接口。原始JSON未改写，AI复核不等同于候选人独立人工签字。

| 场景 | 状态 | 总费用 | 本次费用 | 业务检查 | 实际Trace |
|---|---|---|---|---|---|
| normal | completed | 12 | 12 | PASS | [result](normal/result.json) |
| missing_budget | needs_info | 0 | 0 | PASS | [result](missing_budget/result.json) |
| missing_deadline | needs_info | 0 | 0 | PASS | [result](missing_deadline/result.json) |
| budget_replan | completed | 8 | 8 | PASS | [result](budget_replan/result.json) |
| deadline_replan | completed | 8 | 8 | PASS | [result](deadline_replan/result.json) |
| tool_failure_replan | completed | 11 | 11 | PASS | [result](tool_failure_replan/result.json) |
| persistent_failure | tool_failed | 6 | 6 | PASS | [result](persistent_failure/result.json) |
| no_feasible | constraints_infeasible | 0 | 0 | PASS | [result](no_feasible/result.json) |
| duplicate | completed | 12 | 0 | PASS | [result](duplicate/result.json) |
| resume | completed | 13 | 8 | FAIL | [result](resume/result.json) |
| save_failure_resume | incomplete_model_error | 0 | 0 | FAIL | [result](save_failure_resume/result.json) |
| no_assets | incomplete_model_error | 4 | 4 | FAIL | [result](no_assets/result.json) |
| step_limit | incomplete_step_limit | 4 | 4 | PASS | [result](step_limit/result.json) |

## 复核范围

逐项核对实际费用与attempts账本之和、模拟耗时、预算/截止时间、依赖、成功步骤只收费一次、保存回执与plans表一致，以及跨进程重复/续跑的旧尝试和成功输出保留。至少正常、资料不足、工具失败、预算超限和重复执行均有对应输入及Trace。

## 模型解释文本的限制

deadline_replan第8步短依据误写09:45截止，实际输入为09:50；工具估算和最终输出使用09:50，完成时间09:40未越界。保留原始依据，不把文字误差改写掉。这说明短解释也可能不准确，权限与费用判断应依据结构化工具结果。

单轮业务断言通过不代表稳定成功率；模拟预算不含模型API账单，模拟业务时钟不含网络等待，脚本为模板工具结果。

## 三项未通过及当前决定

resume首段在生成失败后遇到MODEL_TRANSPORT_FAILED，续跑实际完成，但首段不是预期tool_failed，仍记FAIL；save_failure_resume两段均在执行收费工具前发生传输失败，未覆盖真实保存失败恢复；no_assets取得NO_ASSETS后传输失败，未正常结束为needs_materials。详细证据与局限见[评估文档](../../../docs/03-evaluation.md)。传输失败不能凭脱敏日志定位到具体网络或服务端原因。

用户选择保留当前10/13结果、稍后重跑。当前没有重跑记录，不声明全量成功；运行源码与离线摘要一致。
