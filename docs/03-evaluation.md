# 03 预期、实际结果与限制

## 当前验证范围

Python 3.11.4、Windows本机实际执行：**34个自动化测试全部通过，13/13组离线场景通过**。原始结果、Trace和数据库/账本快照位于[examples/runs/mock](../examples/runs/mock/REPORT.md)。[summary.json](../examples/runs/mock/summary.json)记录环境、源码摘要和逐项断言，[tests.txt](../examples/runs/mock/tests.txt)记录测试明细。

离线模型为MockModel，业务工具与SQLite操作实际执行。真实模型deepseek-flash首轮已完成，业务断言10/13通过，三组受到MODEL_TRANSPORT_FAILED影响；用户随后在本机完成三项定向重跑，3/3通过，累计13类场景有通过证据（非一次全量13/13）。原始失败不改写，未将Mock通过当作真实模型证明。

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

## 首轮真实模型结果（原始失败保留）

2026-11-04本机执行，模型deepseek-flash，真实API调用；运行耗时888.984秒（约14.82分钟）。[原始自动报告](../examples/runs/live/REPORT.md)、[原始summary](../examples/runs/live/summary.json)、[AI依据实际Trace及SQLite快照的复核](../examples/runs/live/REVIEW.md)和[逐项账本检查/文件SHA256](../examples/runs/live/review.json)均保留。

真实与离线评估的可执行源码摘要一致：`603706ccb39768d768d287302067faeda7e8a66ac0784af2d052cfa15d1a57ad`。本次只补充证据与文档，没有为通过而改动运行逻辑。原始summary中的`real_model_decision_quality_verified: false`是评估器默认待审标记，未手工改成true；上述单独复核来自AI，不能视为独立人工签字。

| 场景 | 真实实际结果 | 业务断言 | 输入 | 实际输出及Trace |
|---|---|---|---|---|
| 正常 | completed，费用12 | PASS | [input](../examples/runs/live/normal/input.json) | [result](../examples/runs/live/normal/result.json) |
| 缺预算 | needs_info，费用0 | PASS | [input](../examples/runs/live/missing_budget/input.json) | [result](../examples/runs/live/missing_budget/result.json) |
| 缺截止时间 | needs_info，费用0 | PASS | [input](../examples/runs/live/missing_deadline/input.json) | [result](../examples/runs/live/missing_deadline/result.json) |
| 超预算重规划 | 先估12超10，再改lean并完成，费用8 | PASS | [input](../examples/runs/live/budget_replan/input.json) | [result](../examples/runs/live/budget_replan/result.json) |
| 超截止时间重规划 | 先估95分钟超50，再改40分钟方案，费用8 | PASS | [input](../examples/runs/live/deadline_replan/input.json) | [result](../examples/runs/live/deadline_replan/result.json) |
| 单次生成失败 | 保留素材后改lean，完成且总费用11 | PASS | [input](../examples/runs/live/tool_failure_replan/input.json) | [result](../examples/runs/live/tool_failure_replan/result.json) |
| 持续生成失败 | tool_failed，保留素材和两次失败账本，费用6 | PASS | [input](../examples/runs/live/persistent_failure/input.json) | [result](../examples/runs/live/persistent_failure/result.json) |
| 无可行方案 | constraints_infeasible，费用0 | PASS | [input](../examples/runs/live/no_feasible/input.json) | [result](../examples/runs/live/no_feasible/result.json) |
| 重复执行 | 复用原方案，总费用12，本次0 | PASS | [input](../examples/runs/live/duplicate/input.json) | [首次](../examples/runs/live/duplicate/first_run.json)、[重复](../examples/runs/live/duplicate/result.json) |
| 失败后续跑 | 首段网络中断；续跑复用素材并完成，总费用13 | FAIL（首段状态不符预期） | [input](../examples/runs/live/resume/input.json) | [首段](../examples/runs/live/resume/first_run.json)、[续跑](../examples/runs/live/resume/result.json) |
| 保存失败后续跑 | 两段网络中断，尚未执行到保存，费用0 | FAIL | [input](../examples/runs/live/save_failure_resume/input.json) | [首段](../examples/runs/live/save_failure_resume/first_run.json)、[续跑](../examples/runs/live/save_failure_resume/result.json) |
| 无资料 | 取得NO_ASSETS后网络中断，费用4，未保存 | FAIL | [input](../examples/runs/live/no_assets/input.json) | [result](../examples/runs/live/no_assets/result.json) |
| 步数上限 | incomplete_step_limit，素材保留、费用4 | PASS | [input](../examples/runs/live/step_limit/input.json) | [result](../examples/runs/live/step_limit/result.json) |

三项失败的具体边界：

- resume首段检索成功花4、一次生成失败花1，之后模型传输失败，故首段是incomplete_model_error而不是预期tool_failed。第二段实际复用同一素材，premium脚本7和保存1，总费用13，仍在预算15内；仅“首段明确工具失败”的断言未通过，保留FAIL。
- save_failure_resume的两段均在业务执行前网络中断，未测试到真实模型下的保存失败恢复。截至首轮，该能力只有离线和自动化证据；后续定向重跑的实际保存失败恢复见下一节。
- no_assets已实际检索并得到NO_ASSETS，支付模拟费用4，模型下一轮传输失败，因此没有按预期正常结束为needs_materials；没有伪称保存成功。

MODEL_TRANSPORT_FAILED只证明请求/响应传输未完成；脱敏记录无法进一步区分本机网络、代理、超时或服务端原因。当前不把失败一概归因于服务商，也不自动回退Mock或抹去已有费用。用户初次选择保留后，于2026-11-04主动运行`py -3.11 scripts/connect_deepseek.py --retry-failed`，新目录live-retry只重跑上述三组，未覆盖首轮文件。

实际动态决策至少有预算12→8和生成失败后保留素材、改剩余方案两条不同真实路径。无可行案例中模型根据inspect提供的价格表直接估算最便宜且最快的lean，仍有费用缺口5及时间缺口20分钟，因此结束；未强制逐一估算两档，这与离线固定策略不同。

全部13组已产生的账本/状态均通过独立于场景状态的复核：费用与实际attempts一致，成功步骤无重复收费，依赖顺序成立，预算及模拟截止时间未越界，保存声明与plans表一致。此结论不等于13组业务场景全通过。

解释文本也存在限制：deadline_replan第8步依据把截止时间误写为09:45，实际输入09:50，工具和保存数据仍用09:50，实际模拟完成09:40。原文未改写；约束判断依赖结构化输入和工具结果，不能只读模型解释。

## 三项定向重跑（3/3通过，同一运行源码）

2026-11-04用户在本机运行，deepseek-flash，耗时356.641秒（约5.94分钟）。[原始报告](../examples/runs/live-retry/REPORT.md)、[原始summary](../examples/runs/live-retry/summary.json)、[Trace及账本复核](../examples/runs/live-retry/REVIEW.md)、[检查和文件摘要](../examples/runs/live-retry/review.json)均已提交。[两轮完整对应表](../examples/runs/LIVE-REVIEW.md)及[JSON汇总](../examples/runs/live-comparison.json)说明每类场景选用哪一轮的通过证据。

| 场景 | 预期与真实实际 | 输入 | 首段/续跑实际输出与Trace |
|---|---|---|---|
| resume | 首段tool_failed、已花6，素材保留；续跑复用素材，premium脚本7、保存1，新增8、总14≤预算15，10:45完成，PASS | [input](../examples/runs/live-retry/resume/input.json) | [首段](../examples/runs/live-retry/resume/first_run.json)、[续跑](../examples/runs/live-retry/resume/result.json) |
| save_failure_resume | 首段保存失败两次，素材/脚本已成功、费用11，无方案；续跑只补保存1，总12，成功结果和旧失败尝试保留，PASS | [input](../examples/runs/live-retry/save_failure_resume/input.json) | [首段](../examples/runs/live-retry/save_failure_resume/first_run.json)、[续跑](../examples/runs/live-retry/save_failure_resume/result.json) |
| no_assets | premium检索无素材花4，估算后改lean检索仍无素材花2，结束needs_materials，总6、未保存，PASS | [input](../examples/runs/live-retry/no_assets/input.json) | [实际结果](../examples/runs/live-retry/no_assets/result.json) |

首轮10/13、定向重跑3/3，因此累计13类场景均有通过证据。两轮与离线的可执行源码摘要完全相同，未改运行逻辑、未把旧FAIL改成PASS。此统计不是一次全量13/13，不代表稳定成功率。每轮各场景从独立的新评估数据库开始；续跑场景内部的首段与第二段共享同一数据库并重新连接，证明的是该场景跨调用状态恢复。本轮费用不与首轮独立场景相加，不能将这次新评估称为在首轮中断的数据库上原地续跑。

真实模型选择未必最省钱：resume续跑选择可行premium，总14；离线选择lean，总12。no_assets真实尝试两档检索花6，离线一次检索花4。当前验收约束是预算内、事实正确及合理停止，不宣称最优费用。resume续跑第2步短依据在估算前猜11–13，工具实际估算14，后续动作与保存按14执行；保留原始文字误差，仍以工具账本为准。

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

## 新增连续流量结果

[完整连续需求评估](08-product-traffic.md)：两天96条，离线业务目标完成25条、边界检查96条；当前36个回归测试通过。历史真实结果保留，本轮真实流量结果见下节。

## 2026-11-05真实运行

真实连续请求24条，业务目标完成4条，边界检查24/24；耗时945.39秒。[原始报告](../examples/traffic/live-20261104-20261105-011624-777280/REPORT.md)、[Trace复核](../examples/traffic/live-20261104-20261105-011624-777280/REVIEW.md)、[文件及事实核查](../examples/traffic/live-20261104-20261105-011624-777280/review.json)。原始失败保留，不宣称单次通过率能代表生产可靠性。
