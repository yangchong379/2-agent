# 03 预期、实际结果与限制

## 当前验证范围

Python 3.11.4、Windows本机实际执行：**34个自动化测试全部通过，13/13组离线场景通过**。原始结果、Trace和数据库/账本快照位于[examples/runs/mock](../examples/runs/mock/REPORT.md)。[summary.json](../examples/runs/mock/summary.json)记录环境、源码摘要和逐项断言，[tests.txt](../examples/runs/mock/tests.txt)记录测试明细。

本页当前离线结果的模型为MockModel，业务工具与SQLite操作实际执行。用户已启动真实DeepSeek评估，真实结果待核查后另行补充；不把离线通过当作真实模型ReAct效果证明，也不预写真实成功日志。

复核命令（选择新目录保留提交证据）：

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py --output .runtime/recheck-1
```

## 场景预期与实际

| 场景 | 预期 | 离线实际 | 实际结果/Trace |
|---|---|---|---|
| 正常完成 | 依赖完整、费用和时间可行、保存成功 | completed；总费用12、95分钟 | [normal](../examples/runs/mock/normal/result.json) |
| 缺预算 | 列出缺项，不收费 | needs_info；费用0 | [missing_budget](../examples/runs/mock/missing_budget/result.json) |
| 缺截止时间 | 列出缺项，不收费 | needs_info；费用0 | [missing_deadline](../examples/runs/mock/missing_deadline/result.json) |
| 预算超限重规划 | 观察12超出10，改用8 | completed；lean、费用8 | [budget_replan](../examples/runs/mock/budget_replan/result.json) |
| 截止时间重规划 | 95分钟超出50，改40分钟 | completed；lean、费用8 | [deadline_replan](../examples/runs/mock/deadline_replan/result.json) |
| 单次工具失败 | 失败记账，保留素材后重规划 | completed；费用11，检索只做一次 | [tool_failure_replan](../examples/runs/mock/tool_failure_replan/result.json) |
| 持续工具失败 | 明确未完成，保留成功素材 | tool_failed；费用6，脚本failed | [persistent_failure](../examples/runs/mock/persistent_failure/result.json) |
| 无可行方案 | 不执行收费工作，返回两档缺口 | constraints_infeasible；费用0 | [no_feasible](../examples/runs/mock/no_feasible/result.json) |
| 重复执行 | 原方案复用，新增费用0 | completed；总费用12、本次0 | [first](../examples/runs/mock/duplicate/first_run.json)、[repeat](../examples/runs/mock/duplicate/result.json) |
| 失败后续跑 | 重新开库后复用素材 | completed；原费用6，本次6，总12 | [first](../examples/runs/mock/resume/first_run.json)、[resumed](../examples/runs/mock/resume/result.json) |
| 保存失败后续跑 | 素材/脚本不重复执行，只补保存 | completed；本次仅1，总12 | [first](../examples/runs/mock/save_failure_resume/first_run.json)、[resumed](../examples/runs/mock/save_failure_resume/result.json) |
| 无资料 | 付出检索费用但未得素材，明确不足 | needs_materials；费用4 | [no_assets](../examples/runs/mock/no_assets/result.json) |
| 步数上限 | 保存已有部分成功结果，明确未完成 | incomplete_step_limit；保留素材、费用4 | [step_limit](../examples/runs/mock/step_limit/result.json) |

每组目录都有input.json、dataset.json、result.json（含trace）和database_snapshot.json。测试结果及评估文件集中在examples，满足至少正常、资料不足、工具失败三组材料及全部必验收点。保存失败记录中的“无方案”与已成功素材/脚本同时保留，不等于全部执行失败。

## 可观察的决策差异

- 正常：读取状态→估算premium可行→检索→按新状态再估算→生成→再估算→保存→结束。
- 预算10：估算premium得到预计12、缺口2→改估lean预计8→按lean执行并保存。
- 生成单次失败：premium检索成功花4→生成失败花1→改估lean剩余6、预计总11→复用原素材生成脚本→保存。
- 持续失败：本轮两次生成失败后结束，任务保留成功素材、两次失败尝试及费用6。
- 续跑：重新创建Store连接，读取已成功素材；生成和保存完成后累计费用12，没有再次检索。

以上是对实际Mock Trace的摘要。真实模式中的选择由远端模型决定，可以有不同顺序；不能用这些摘要伪装成真实模型日志。

## 费用与状态核对

评估断言检查费用合计等于数据库attempts账本之和、实际费用不超过预算、模拟时钟不超过截止时间、方案保存声明与plans表一致、重跑成功步骤的ID保持不变、重复执行新增费用和业务尝试数均为0。

单次生成失败案例的总价11由4（成功检索）+1（失败尝试）+5（成功轻量脚本）+1（保存）组成。失败步骤只有在新的尝试确实成功后才更新最新状态，早先failed记录仍在attempts中，不能删掉失败费用后宣称只花8。

测试还覆盖：并发检索只收费一次；依赖未满足拒绝；过期估算拒绝；预算/截止时间不能由模型参数覆盖；同ID修改要求拒绝；SQLite保存插入被触发器中断时，方案、费用和步骤一并回滚；协议拒绝与错误脱敏；CLI退出码；本机密钥不打印及环境清理。模型适配器使用伪造HTTP响应的测试不是远端模型实测。

## 限制与待验证内容

1. 本地素材、脚本模板、工具费用与耗时为合成模拟。API收费不在模拟预算内；业务时钟不计模型网络等待，不代表生产交付时效保证。
2. 相同request_id为同一活动幂等键；不同ID视为不同活动，不跨活动共享缓存或退款。修改预算/截止时间须新ID，不能偷偷扩大旧任务权限。
3. 工具失败费用按数据表计入；保存故障注入是明确的业务模拟。SQL触发器回滚测试证明本地事务边界，不覆盖跨服务“已完成但响应丢失”的账单问题。
4. 任务状态持久化与Trace分离；生产环境仍需用户认证、操作审计、凭据管理、账单对账及真实耗时预测。
5. 真实模型可能输出不合规调用、选较差但合法的方案或在步数上限前未完成；没有可靠性百分比结论。GitHub Actions配置已提供，云端CI状态以仓库实际运行页为准。

## 真实评估入口

本机执行`py -3.11 scripts/connect_deepseek.py --evaluate`，评估自动选择新的live目录；失败后用`--retry-failed`只重跑最新一轮仍失败的项。至少检查预算12→8、工具失败后保留成果、无可行方案返回缺口、重复/续跑不重扣费用。保留失败与修复后的不同目录和源码摘要，不能把多轮累计通过说成一次全量成功率。
