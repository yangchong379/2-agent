# 连续混合需求运行记录

一个共享数据库，按顺序多运营请求；重复、同ID改条件、业务故障与外部占位混在流量中，不逐案例清库。模拟运营确认事件只批准真实返回的待确认时段，参数在每条input中保存；不冒称真实用户授权。自然语言理解不在旧产品入口范围，需求已由模拟运营端提交为结构化表单。

模式：live_model；需求24条，业务目标完成4条，边界/状态检查24/24。

业务目标完成数与安全检查分开：风险阻断、缺资料、冲突待确认及输入拒绝可能是正确响应，但不计为已完成业务。不要把边界检查全过称为全部需求完成。

[固定需求流](demand-stream.json) · [数据](dataset.json) · [逐项统计](summary.json)

| 到达序号 | 实际状态 | 业务目标 | 边界检查 | 输出及Trace |
|---|---|---|---|---|
| 1 | needs_info | 未完成/待处理 | PASS | [result](001/result.json) |
| 2 | constraints_infeasible | 未完成/待处理 | PASS | [result](002/result.json) |
| 3 | constraints_infeasible | 未完成/待处理 | PASS | [result](003/result.json) |
| 4 | needs_info | 未完成/待处理 | PASS | [result](004/result.json) |
| 5 | completed | 完成 | PASS | [result](005/result.json) |
| 6 | constraints_infeasible | 未完成/待处理 | PASS | [result](006/result.json) |
| 7 | constraints_infeasible | 未完成/待处理 | PASS | [result](007/result.json) |
| 8 | tool_failed | 未完成/待处理 | PASS | [result](008/result.json) |
| 9 | constraints_infeasible | 未完成/待处理 | PASS | [result](009/result.json) |
| 10 | constraints_infeasible | 未完成/待处理 | PASS | [result](010/result.json) |
| 11 | completed | 完成 | PASS | [result](011/result.json) |
| 12 | request_rejected | 未完成/待处理 | PASS | [result](012/result.json) |
| 13 | constraints_infeasible | 未完成/待处理 | PASS | [result](013/result.json) |
| 14 | constraints_infeasible | 未完成/待处理 | PASS | [result](014/result.json) |
| 15 | completed | 完成 | PASS | [result](015/result.json) |
| 16 | constraints_infeasible | 未完成/待处理 | PASS | [result](016/result.json) |
| 17 | constraints_infeasible | 未完成/待处理 | PASS | [result](017/result.json) |
| 18 | needs_info | 未完成/待处理 | PASS | [result](018/result.json) |
| 19 | constraints_infeasible | 未完成/待处理 | PASS | [result](019/result.json) |
| 20 | constraints_infeasible | 未完成/待处理 | PASS | [result](020/result.json) |
| 21 | needs_info | 未完成/待处理 | PASS | [result](021/result.json) |
| 22 | needs_info | 未完成/待处理 | PASS | [result](022/result.json) |
| 23 | needs_info | 未完成/待处理 | PASS | [result](023/result.json) |
| 24 | completed | 完成 | PASS | [result](024/result.json) |

每个编号目录含input、result及前后全量状态快照；未入Git的state.sqlite仅本机续跑。故障是预先抽样的服务事件，不代表实际服务故障率。任务规划每任务独立预算；没有全公司共享钱包/排队资源，模拟时间不计API等待。排期外部占位可能使旧草稿过期；测试不会把它们当成已发布。
