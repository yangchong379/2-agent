# 内容任务规划 Agent · 题目2

帮助运营人员在预算与截止时间内完成内容活动方案。提供任务计划、逐步状态、素材/脚本结果、实际费用账本、已保存方案或明确未完成原因。CLI运行，Python标准库原生实现，无Agent框架依赖。

项目仓库：[yangchong379/2-agent](https://github.com/yangchong379/2-agent)。这是独立项目；素材审核与排期项目位于另一个仓库。本项目的工具调用协议与本机密码输入复用了前一项目中已验证的通用适配逻辑，预算、任务状态与计费模块独立实现，不依赖另一目录。

**当前已验证：34个自动化测试通过，13组离线场景通过。真实模型评估已由用户启动，结果待核查；不能把Mock当作模型效果证明。**

## 评审入口

| 材料 | 入口 |
|---|---|
| 需求、范围与验收映射 | [docs/01-requirements.md](docs/01-requirements.md) |
| 动态规划、计费和持久化设计 | [docs/02-solution.md](docs/02-solution.md) |
| 预期、实际结果、失败与限制 | [docs/03-evaluation.md](docs/03-evaluation.md) |
| AI辅助、个人贡献及复用范围 | [docs/04-ai-usage.md](docs/04-ai-usage.md) |
| 难点、收获、实际用时与下一步 | [docs/05-retrospective.md](docs/05-retrospective.md) |
| 离线实际结果 | [examples/runs/mock/REPORT.md](examples/runs/mock/REPORT.md) |
| 实际测试明细 | [examples/runs/mock/tests.txt](examples/runs/mock/tests.txt) |
| 环境和源码摘要 | [examples/runs/mock/summary.json](examples/runs/mock/summary.json) |

## 环境、安装和运行

Python **3.11+**；本机实测3.11.4。运行和测试仅使用标准库（sqlite3、urllib、unittest等），Windows密钥窗口使用Python自带tkinter。无需安装第三方包。所有命令在本仓库根目录执行，Windows可将`python`换成`py -3.11`。

```bash
python scripts/run.py --input examples/inputs/budget_replan.json --db .runtime/demo.sqlite --output .runtime/demo.json
python -m unittest discover -s tests -v
# 提交的证据不覆盖，复核另选目录：
python scripts/evaluate.py --output .runtime/recheck-1
```

可选安装：`python -m pip install -e .`，然后使用`content-agent`或`python -m content_agent`。`.env.example`仅说明变量，**不会自动加载**。

## 输入和业务约束

```json
{
  "request_id": "summer-001",
  "topic": "夏日旅行",
  "budget": 10,
  "start_at": "2026-11-05T09:00+08:00",
  "deadline": "2026-11-05T11:30+08:00"
}
```

- budget为非负整数模拟单位，0是有效上限；缺预算或截止时间会返回needs_info，不执行收费步骤。
- start_at是可选的模拟业务时钟起点；省略时首次创建任务记录本机时间，后续同请求保持该起点。示例固定日期用于复现。
- 所有时间显式带`+08:00`。工具耗时是合成业务分钟，**不包含真实模型/网络等待**，不是实际交付时效承诺。
- 模拟预算不包含DeepSeek真实API账单；模型调用费用另由服务商计费。
- 同request_id须对应相同主题、预算、截止时间和起点；更改要求需新ID。工具没有修改用户预算或截止时间的参数。

## 预算重规划实例

| 方案 | 检索素材 | 生成脚本 | 保存方案 | 合计费用 | 合计模拟耗时 |
|---|---|---|---|---|---|
| premium | 4 / 20分钟 | 7 / 70分钟 | 1 / 5分钟 | 12 | 95分钟 |
| lean | 2 / 10分钟 | 5 / 25分钟 | 1 / 5分钟 | 8 | 40分钟 |

预算10时，模型先估算premium得到超出2单位，再估算lean并执行，总费用8。每次工具尝试后要按新状态重新估算，成功步骤从剩余工作中扣除。

生成失败场景的预算为15：premium检索已花4，生成失败花1；改用lean且复用已有素材，剩余脚本5、保存1，最终实际费用是 **4+1+5+1=11**。不能把lean的基础报价8当作已经发生费用后的最终总价。

脚本工具是本地合成模板，素材也是合成资料；真实模式检验的是模型选择工具、调整方案和结束的决策，不证明真实内容创作质量。

## 状态保留、重复执行与续跑

成功素材和脚本、失败尝试、费用和模拟耗时都持久化。步骤依赖为`search_assets → generate_script → save_plan`。失败记录保留在attempts，只有之后实际成功的新尝试才使步骤最新状态成为succeeded。

```bash
# 第一轮生成持续失败，预期退出码2，已检索素材保留：
python scripts/run.py --input examples/inputs/resume.json --db .runtime/resume.sqlite --fault generate_script_always --output .runtime/failed.json
# 移除故障，复用同输入和同数据库续跑：
python scripts/run.py --input examples/inputs/resume.json --db .runtime/resume.sqlite --output .runtime/resumed.json
# 再执行一次：已有方案复用，本次费用为0：
python scripts/run.py --input examples/inputs/resume.json --db .runtime/resume.sqlite --output .runtime/duplicate.json
```

数据库事务将输出、费用与时间一并提交，方案按request_id唯一；并发重复步骤只实际执行/收费一次。复用依据数据库成功事实，不能仅相信模型文字。换数据/价格表须新数据库，避免破坏旧费用证据。

## 真实模型评估

在本机PowerShell中执行，密码在弹窗中输入，不发送到聊天或仓库：

```powershell
py -3.11 scripts/connect_deepseek.py
# 全部13组，会产生多次真实API调用：
py -3.11 scripts/connect_deepseek.py --evaluate
# 只重跑最新一轮仍失败的场景：
py -3.11 scripts/connect_deepseek.py --retry-failed
```

新评估自动选择新的live目录，保留旧证据。最新轮无失败时，重跑入口不会索取密钥或调用模型。自定义兼容接口可使用环境变量`MODEL_BASE_URL`、`MODEL_NAME`、`MODEL_API_KEY`、`MODEL_THINKING`，再运行`--model live`。接口配置依据：[DeepSeek首次调用](https://api-docs.deepseek.com/)、[工具调用](https://api-docs.deepseek.com/guides/tool_calls/)。

真实模式每一步均由远端模型返回工具调用；Python执行后把实际观察回传。零/多调用和不合规短依据会明确拒绝，模型可在步数预算内纠正；不会自动切换Mock。默认全请求40步，可设1–100；耗尽返回incomplete_step_limit并保留成功结果。原始内部思考内容不写入Trace。

## 输出与退出码

结果含task_plan、步骤依赖和状态、工具结果、estimates、attempts、actual_cost_total、charged_this_invocation、saved_plan或uncompleted_reason，以及带参数/观察/下一步的Trace。

| 退出码 | 意义 |
|---|---|
| 0 | completed，方案有真实数据库保存回执 |
| 2 | 本轮明确未完成：缺输入、不可行、资料不足或工具失败 |
| 3 | 达到步数上限或模型错误，部分成功结果仍保留 |
| 4 | 输入、配置、文件或数据库初始化错误 |

成本、时间、脚本和素材均为合成业务模拟；无真实发布接口。多人认证、跨服务账单、真实耗时预测、任务撤销和跨请求结果共享不在当前范围。GitHub最新提交SHA用`git rev-parse HEAD`获取，提交信息见[SUBMISSION.md](SUBMISSION.md)。
