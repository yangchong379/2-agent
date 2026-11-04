# 考核提交入口

- 题号：**2 · 内容任务规划 Agent**（用户已确认页面题号）。
- GitHub：[yangchong379/2-agent](https://github.com/yangchong379/2-agent)。
- 分支：main；最终完整commit SHA使用`git rev-parse HEAD`并与远端核对。
- 运行与评审：[README](README.md)。
- 当前证据：34个自动化测试通过，13/13组离线场景通过；DeepSeek真实模型首轮10/13通过，三项传输错误定向重跑3/3通过；两轮源码相同，累计13类场景均有通过证据，非一次全量13/13或稳定成功率。首轮失败完整保留。Mock仅验证流程。

至少正常、缺预算/截止时间、工具失败、预算超限、重复执行均有输入、实际输出和Trace；另覆盖跨进程失败续跑、保存失败后只补保存、无可行方案和步数上限。两轮真实材料汇总见[运行证据](examples/runs/LIVE-REVIEW.md)，详细材料见[评估文档](docs/03-evaluation.md)。

项目采用Python标准库，无Agent框架。业务工具、费用和耗时为合成模拟；真实模型入口提供DeepSeek工具调用。模型Mock仅验证流程，不作为真实模型决策证明。AI辅助与个人贡献分工见[AI使用记录](docs/04-ai-usage.md)。
