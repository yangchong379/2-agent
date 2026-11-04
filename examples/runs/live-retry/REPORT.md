# Actual evaluation report

Mode: **live_model**

Mock proves workflow only; live mode uses actual model decisions with synthetic tools.

| Case | Expected | Actual | Total simulated cost | Checks |
|---|---|---|---|---|
| [resume](resume/result.json) | completed | completed | 14 | PASS |
| [save_failure_resume](save_failure_resume/result.json) | completed | completed | 12 | PASS |
| [no_assets](no_assets/result.json) | needs_materials | needs_materials | 6 | PASS |

Passed: 3/3

Source SHA-256: `603706ccb39768d768d287302067faeda7e8a66ac0784af2d052cfa15d1a57ad`
