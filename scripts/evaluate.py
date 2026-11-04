"""Generate actual input/output/trace/ledger evidence. Mock is not live model evidence."""
import argparse
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from content_agent.cli import read_json, write_json
from content_agent.domain import digest, timestamp
from content_agent.engine import Agent
from content_agent.models import ChatModel, MockModel
from content_agent.store import Store


def request(name, **extra):
    return {"request_id": name, "topic": "夏日旅行", "budget": 15,
            "start_at": "2026-11-05T09:00+08:00", "deadline": "2026-11-05T11:30+08:00", **extra}


def cases():
    return [
        ("normal", request("normal"), "completed", None, 40),
        ("missing_budget", request("missing_budget", budget=None), "needs_info", None, 40),
        ("missing_deadline", request("missing_deadline", deadline=None), "needs_info", None, 40),
        ("budget_replan", request("budget_replan", budget=10), "completed", None, 40),
        ("deadline_replan", request("deadline_replan", deadline="2026-11-05T09:50+08:00"), "completed", None, 40),
        ("tool_failure_replan", request("tool_failure_replan"), "completed", "generate_script_once", 40),
        ("persistent_failure", request("persistent_failure"), "tool_failed", "generate_script_always", 40),
        ("no_feasible", request("no_feasible", budget=3, deadline="2026-11-05T09:20+08:00"), "constraints_infeasible", None, 40),
        ("duplicate", request("duplicate"), "completed", None, 40),
        ("resume", request("resume"), "completed", None, 40),
        ("save_failure_resume", request("save_failure_resume"), "completed", None, 40),
        ("no_assets", request("no_assets", topic="不存在的主题"), "needs_materials", None, 40),
        ("step_limit", request("step_limit"), "incomplete_step_limit", None, 3),
    ]


def source_digest():
    return digest({str(p.relative_to(ROOT)).replace("\\", "/"): p.read_text(encoding="utf-8")
                   for folder in ("src", "tests", "scripts") for p in sorted((ROOT / folder).rglob("*.py"))})


def evaluate(mode, destination, case_names=None):
    selected = cases()
    if case_names is not None:
        if not case_names or len(case_names) != len(set(case_names)) or set(case_names) - {c[0] for c in selected}:
            raise ValueError("choose nonempty unique known cases")
        selected = [c for c in selected if c[0] in case_names]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "summary.json").exists():
        raise ValueError("output already contains a completed run; choose a new directory to preserve evidence")
    data = read_json(ROOT / "data/fixtures.json")
    summary = {"mode": "offline_mock" if mode == "mock" else "live_model",
               "generated_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
               "platform": platform.platform(), "source_sha256": source_digest(), "cases": [],
               "boundary": "Simulated business tools, prices and durations; inspect actual live traces before claiming model decision quality.",
               "real_model_decision_quality_verified": False}
    started = time.monotonic()
    for name, req, expected, fault, limit in selected:
        folder = destination / name
        write_json(ROOT / "examples/inputs" / f"{name}.json", req)
        write_json(folder / "input.json", req)
        write_json(folder / "dataset.json", data)
        first = None
        def model():
            return MockModel() if mode == "mock" else ChatModel()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "planner.sqlite"
            store = Store(path, data)
            try:
                if name in {"duplicate", "resume", "save_failure_resume"}:
                    first_fault = {"duplicate": None, "resume": "generate_script_always", "save_failure_resume": "save_plan_always"}[name]
                    first = Agent(model(), store, data, fault=first_fault).run(copy.deepcopy(req))
                    write_json(folder / "first_run.json", first)
                    store.close()
                    store = Store(path, data)  # Prove persistence, not just in-memory reuse.
                result = Agent(model(), store, data, max_steps=limit, fault=fault).run(copy.deepcopy(req))
                snapshot = store.snapshot(req["request_id"])
                write_json(folder / "result.json", result)
                write_json(folder / "database_snapshot.json", snapshot)
            finally:
                store.close()
        checks = {"expected_status": result["status"] == expected,
                  "exact_ledger_sum": result["actual_cost_total"] == sum(a["cost"] for a in snapshot["ledger"]),
                  "no_publication": result["published"] is False,
                  "bounded": result["model_calls"] <= limit,
                  "no_false_saved_claim": (result["saved_plan"] is None and not snapshot["plans"]) or
                        bool(result["saved_plan"]) and len(snapshot["plans"]) == 1 and snapshot["plans"][0]["id"] == result["saved_plan"]["id"]}
        if req["budget"] is not None:
            checks["actual_cost_within_budget"] = result["actual_cost_total"] <= req["budget"]
        if req["deadline"] is not None:
            checks["simulated_time_within_deadline"] = timestamp(result["business_clock"]) <= timestamp(req["deadline"])
        if name == "budget_replan":
            checks["observed_overbudget_then_feasible"] = any(e["budget_gap"] > 0 for e in result["estimates"]) and result["selected_plan"] == "lean"
        if name == "deadline_replan":
            checks["observed_deadline_gap_then_feasible"] = any(e["deadline_gap_minutes"] > 0 for e in result["estimates"]) and result["selected_plan"] == "lean"
        if name == "tool_failure_replan":
            checks["failed_attempt_visible"] = any(a["status"] == "failed" for a in result["attempts"])
            checks["search_not_repeated"] = sum(a["tool"] == "search_assets" for a in result["attempts"]) == 1
        if name in {"missing_budget", "missing_deadline", "no_feasible"}:
            checks["no_execution_charge"] = result["actual_cost_total"] == 0
        if first:
            checks["successful_asset_retained"] = result["task_plan"][0]["step_id"] == first["task_plan"][0]["step_id"]
            checks["search_executed_once"] = sum(a["tool"] == "search_assets" for a in result["attempts"]) == 1
            if name == "duplicate":
                checks["same_plan_id"] = bool(first["saved_plan"]) and bool(result["saved_plan"]) and first["saved_plan"]["id"] == result["saved_plan"]["id"]
                checks["no_rebilling"] = result["charged_this_invocation"] == result["business_attempts_this_invocation"] == 0
            else:
                checks["first_was_explicit_failure"] = first["status"] == "tool_failed" and first["saved_plan"] is None
                checks["resume_successful"] = result["status"] == "completed"
            if name == "save_failure_resume":
                checks["successful_script_retained"] = result["task_plan"][1]["step_id"] == first["task_plan"][1]["step_id"]
                checks["charged_only_save"] = result["charged_this_invocation"] == 1
        record = {"case": name, "expected_status": expected, "actual_status": result["status"],
                  "actual_cost_total": result["actual_cost_total"], "charged_this_invocation": result["charged_this_invocation"],
                  "checks": checks, "passed": all(checks.values()), "result": f"{name}/result.json"}
        summary["cases"].append(record)
        print(f"{name}: {'PASS' if record['passed'] else 'FAIL'} ({result['status']}, total={result['actual_cost_total']}, new={result['charged_this_invocation']})", flush=True)
    summary.update(duration_seconds=round(time.monotonic() - started, 3),
                   passed=sum(c["passed"] for c in summary["cases"]), total=len(summary["cases"]))
    if mode == "mock":
        stream = io.StringIO()
        test_result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
        (destination / "tests.txt").write_text(stream.getvalue(), encoding="utf-8")
        summary["unit_tests"] = {"run": test_result.testsRun, "passed": test_result.wasSuccessful(),
                                 "failures": len(test_result.failures), "errors": len(test_result.errors)}
    write_json(destination / "summary.json", summary)
    lines = ["# Actual evaluation report", "", f"Mode: **{summary['mode']}**", "",
             "Mock proves workflow only; live mode uses actual model decisions with synthetic tools.", "",
             "| Case | Expected | Actual | Total simulated cost | Checks |", "|---|---|---|---|---|"]
    lines += [f"| [{r['case']}]({r['result']}) | {r['expected_status']} | {r['actual_status']} | {r['actual_cost_total']} | {'PASS' if r['passed'] else 'FAIL'} |" for r in summary["cases"]]
    lines += ["", f"Passed: {summary['passed']}/{summary['total']}", "", f"Source SHA-256: `{summary['source_sha256']}`", ""]
    (destination / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if summary["passed"] == summary["total"] and summary.get("unit_tests", {}).get("passed", True) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["mock", "live"], default="mock")
    parser.add_argument("--output", default=None)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    output = args.output or str(ROOT / "examples/runs" / args.model)
    try:
        raise SystemExit(evaluate(args.model, output, args.cases))
    except ValueError as exc:
        parser.exit(4, f"Configuration error: {exc}\n")
