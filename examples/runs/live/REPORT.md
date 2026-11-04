# Actual evaluation report

Mode: **live_model**

Mock proves workflow only; live mode uses actual model decisions with synthetic tools.

| Case | Expected | Actual | Total simulated cost | Checks |
|---|---|---|---|---|
| [normal](normal/result.json) | completed | completed | 12 | PASS |
| [missing_budget](missing_budget/result.json) | needs_info | needs_info | 0 | PASS |
| [missing_deadline](missing_deadline/result.json) | needs_info | needs_info | 0 | PASS |
| [budget_replan](budget_replan/result.json) | completed | completed | 8 | PASS |
| [deadline_replan](deadline_replan/result.json) | completed | completed | 8 | PASS |
| [tool_failure_replan](tool_failure_replan/result.json) | completed | completed | 11 | PASS |
| [persistent_failure](persistent_failure/result.json) | tool_failed | tool_failed | 6 | PASS |
| [no_feasible](no_feasible/result.json) | constraints_infeasible | constraints_infeasible | 0 | PASS |
| [duplicate](duplicate/result.json) | completed | completed | 12 | PASS |
| [resume](resume/result.json) | completed | completed | 13 | FAIL |
| [save_failure_resume](save_failure_resume/result.json) | completed | incomplete_model_error | 0 | FAIL |
| [no_assets](no_assets/result.json) | needs_materials | incomplete_model_error | 4 | FAIL |
| [step_limit](step_limit/result.json) | incomplete_step_limit | incomplete_step_limit | 4 | PASS |

Passed: 10/13

Source SHA-256: `603706ccb39768d768d287302067faeda7e8a66ac0784af2d052cfa15d1a57ad`
