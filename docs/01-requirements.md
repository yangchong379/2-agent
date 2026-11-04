# 01 需求、范围与成功标准

题号2：内容任务规划Agent。用户是运营人员，目标是在不可擅改的预算与截止时间下形成可保存的内容活动方案，并在工具失败或资源受限时保留已完成工作。

输入为主题、预算、截止时间和可选模拟起点；材料为合成素材库与两档工具费用/耗时表。交付为计划、依赖、每步状态、素材和脚本、实际总费用、保存方案或未完成原因。CLI为运行入口，不做界面、部署或真实发布。

## 验收与材料映射

每个目录包含input.json、dataset.json、result.json（含trace）和database_snapshot.json；重复/续跑另有first_run.json。下表当前为离线实际运行，Mock不证明真实模型决策效果。

| 必验收项 | 成功标准 | 输入 | 实际输出/运行记录 |
|---|---|---|---|
| 正常完成 | 依赖满足、费用/时间未超限、方案确实保存 | [normal](../examples/runs/mock/normal/input.json) | [result](../examples/runs/mock/normal/result.json) |
| 缺预算 | needs_info，零费用，不保存 | [missing_budget](../examples/runs/mock/missing_budget/input.json) | [result](../examples/runs/mock/missing_budget/result.json) |
| 缺截止时间 | needs_info，零费用，不保存 | [missing_deadline](../examples/runs/mock/missing_deadline/input.json) | [result](../examples/runs/mock/missing_deadline/result.json) |
| 工具失败 | 失败尝试如实记录、成功素材保留、可重规划 | [tool_failure_replan](../examples/runs/mock/tool_failure_replan/input.json) | [result](../examples/runs/mock/tool_failure_replan/result.json) |
| 预算超限 | 观察12超出预算10，改估8并完成；无可行则返回缺口 | [budget_replan](../examples/runs/mock/budget_replan/input.json) | [result](../examples/runs/mock/budget_replan/result.json)、[不可行](../examples/runs/mock/no_feasible/result.json) |
| 重复执行 | 返回同方案ID，新增费用0，方案/账本不重复 | [duplicate](../examples/runs/mock/duplicate/input.json) | [first](../examples/runs/mock/duplicate/first_run.json)、[repeat](../examples/runs/mock/duplicate/result.json) |
| 续跑加分 | 重新打开数据库后只做未完成步骤 | [resume](../examples/runs/mock/resume/input.json) | [first](../examples/runs/mock/resume/first_run.json)、[resumed](../examples/runs/mock/resume/result.json) |

额外覆盖截止时间重规划、持续失败明确停止、保存失败后只补保存、检索无资料、达到步数上限。

## 状态和预算边界

1. 估算只提供预测；actual_cost_total来自已提交的attempts账本，失败费用也计入。
2. 依赖成功是执行前提；模型不能自填成功、修改预算/截止时间或跳过保存工具。
3. 成功步骤的结果在重规划/重试/重新进程运行后保留；切换方案不退款，重新执行成功步骤不收费。
4. 同ID修改输入拒绝；同ID相同输入复用一个持久任务和一个已保存方案。
5. 模拟时钟和费用用于验证约束推理，不是实际工期和真实API账单。

素材可由premium检索后用于lean脚本；已生成成功的脚本固定其方案档位，避免无说明覆盖成功产物。所有素材、脚本、规则无真实隐私数据。
