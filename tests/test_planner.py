from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from content_agent.domain import ORDER, validate_request
from content_agent.engine import Agent
from content_agent.models import Action, ChatModel, MockModel, ModelError, ModelProtocolError
from content_agent.store import Store


def fixtures():
    return json.loads((ROOT / "data/fixtures.json").read_text(encoding="utf-8"))


def request(**extra):
    return {"request_id": "test-run", "topic": "夏日旅行", "budget": 15,
            "start_at": "2026-11-05T09:00+08:00", "deadline": "2026-11-05T11:30+08:00", **extra}


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "planner.sqlite"
        self.data = fixtures()
        self.store = Store(self.path, self.data)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def run_agent(self, req=None, **kwargs):
        return Agent(MockModel(), self.store, self.data, **kwargs).run(req or request())

    def test_normal_completes_with_exact_ledger_and_dependencies(self):
        result = self.run_agent()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["actual_cost_total"], 12)
        self.assertEqual(result["elapsed_business_minutes"], 95)
        self.assertEqual([s["status"] for s in result["task_plan"]], ["succeeded"] * 3)
        self.assertEqual(sum(a["cost"] for a in result["attempts"]), 12)
        self.assertEqual(len(self.store.snapshot("test-run")["plans"]), 1)
        self.assertFalse(result["published"])

    def test_budget_replans_from_twelve_to_eight(self):
        result = self.run_agent(request(budget=10))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["selected_plan"], "lean")
        self.assertEqual(result["actual_cost_total"], 8)
        self.assertEqual(result["estimates"][0]["projected_total_cost"], 12)
        self.assertFalse(result["estimates"][0]["feasible"])
        self.assertEqual(result["estimates"][1]["projected_total_cost"], 8)

    def test_deadline_replans_without_changing_original_deadline(self):
        req = request(deadline="2026-11-05T09:50+08:00")
        result = self.run_agent(req)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["selected_plan"], "lean")
        self.assertEqual(result["elapsed_business_minutes"], 40)
        self.assertEqual(result["request"]["deadline"], req["deadline"])
        self.assertEqual(result["estimates"][0]["deadline_gap_minutes"], 45)

    def test_missing_budget_and_deadline_each_stop_without_charges(self):
        for index, field in enumerate(("budget", "deadline")):
            req = request(request_id=f"missing-{index}")
            req.pop(field)
            result = self.run_agent(req)
            self.assertEqual(result["status"], "needs_info")
            self.assertIn(field, result["missing_fields"])
            self.assertEqual(result["actual_cost_total"], 0)
            self.assertIsNone(result["saved_plan"])

    def test_zero_budget_is_a_limit_not_missing_input(self):
        result = self.run_agent(request(budget=0))
        self.assertEqual(result["status"], "constraints_infeasible")
        self.assertNotIn("budget", result["missing_fields"])

    def test_infeasible_returns_gaps_without_executing_business_tools(self):
        result = self.run_agent(request(budget=3, deadline="2026-11-05T09:20+08:00"))
        self.assertEqual(result["status"], "constraints_infeasible")
        gaps = result["uncompleted_reason"]["constraint_gaps"]
        self.assertEqual({g["plan_id"] for g in gaps}, {"premium", "lean"})
        self.assertTrue(all(g["budget_gap"] > 0 and g["deadline_gap_minutes"] > 0 for g in gaps))
        self.assertEqual(result["actual_cost_total"], 0)

    def test_tool_failure_replans_and_retains_successful_assets(self):
        result = self.run_agent(fault="generate_script_once")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["selected_plan"], "lean")
        self.assertEqual(result["actual_cost_total"], 11)  # 4 assets + 1 failed attempt + 5 script + 1 save
        attempts = result["attempts"]
        self.assertEqual(sum(a["tool"] == "search_assets" for a in attempts), 1)
        generations = [a for a in attempts if a["tool"] == "generate_script"]
        self.assertEqual([a["status"] for a in generations], ["failed", "succeeded"])
        self.assertEqual(result["task_plan"][0]["result"]["materials"][0]["id"], "A01")
        self.assertEqual(result["task_plan"][1]["result"]["asset_ids"], ["A01"])

    def test_persistent_failure_is_not_success_and_keeps_partial_work(self):
        result = self.run_agent(fault="generate_script_always")
        self.assertEqual(result["status"], "tool_failed")
        self.assertEqual(result["actual_cost_total"], 6)
        self.assertEqual(result["task_plan"][0]["status"], "succeeded")
        self.assertEqual(result["task_plan"][1]["status"], "failed")
        self.assertEqual(result["task_plan"][2]["status"], "pending")
        self.assertIsNone(result["saved_plan"])

    def test_failed_step_resumes_after_reopening_database(self):
        first = self.run_agent(fault="generate_script_always")
        asset_id = first["task_plan"][0]["step_id"]
        self.store.close()
        self.store = Store(self.path, self.data)
        second = self.run_agent()
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["actual_cost_total"], 12)
        self.assertEqual(second["charged_this_invocation"], 6)
        self.assertEqual(second["task_plan"][0]["step_id"], asset_id)
        self.assertEqual(sum(a["tool"] == "search_assets" for a in second["attempts"]), 1)

    def test_save_failure_resume_reuses_assets_and_script(self):
        first = self.run_agent(fault="save_plan_always")
        self.assertEqual(first["status"], "tool_failed")
        self.assertEqual(first["actual_cost_total"], 11)
        self.assertIsNone(first["saved_plan"])
        second = self.run_agent()
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["charged_this_invocation"], 1)
        for i in (0, 1):
            self.assertEqual(second["task_plan"][i]["step_id"], first["task_plan"][i]["step_id"])
            self.assertEqual(second["task_plan"][i]["attempt_count"], 1)

    def test_duplicate_run_never_rebills_or_creates_second_plan(self):
        first = self.run_agent()
        second = self.run_agent()
        self.assertEqual(first["saved_plan"], second["saved_plan"])
        self.assertEqual(second["charged_this_invocation"], 0)
        self.assertEqual(second["business_attempts_this_invocation"], 0)
        snapshot = self.store.snapshot("test-run")
        self.assertEqual(len(snapshot["plans"]), 1)
        self.assertEqual(len(snapshot["ledger"]), 3)

    def test_same_request_id_cannot_change_budget_or_deadline(self):
        self.run_agent()
        with self.assertRaisesRegex(ValueError, "REQUEST_ID_REUSED"):
            self.run_agent(request(budget=20))

    def test_default_start_is_persisted_once_on_repeated_request(self):
        req = request()
        req.pop("start_at")
        req = validate_request(req)
        self.store.ensure_run(req)
        first = self.store.state("test-run")["effective_start"]
        self.store.ensure_run(req)
        self.assertEqual(self.store.state("test-run")["effective_start"], first)

    def test_no_assets_records_real_search_fee_and_stops(self):
        result = self.run_agent(request(topic="不存在的主题"))
        self.assertEqual(result["status"], "needs_materials")
        self.assertEqual(result["actual_cost_total"], 4)
        self.assertEqual(result["task_plan"][0]["status"], "failed")
        self.assertIsNone(result["saved_plan"])

    def test_step_limit_returns_partial_work_without_faking_saved(self):
        result = self.run_agent(max_steps=3)
        self.assertEqual(result["status"], "incomplete_step_limit")
        self.assertEqual(result["model_calls"], 3)
        self.assertEqual(result["actual_cost_total"], 4)
        self.assertEqual(result["task_plan"][0]["status"], "succeeded")
        self.assertIsNone(result["saved_plan"])

    def test_new_estimate_required_after_every_charged_attempt(self):
        req = validate_request(request())
        self.store.ensure_run(req)
        self.store.estimate("test-run", "premium")
        self.assertTrue(self.store.execute("test-run", "search_assets", "premium")["ok"])
        result = self.store.execute("test-run", "generate_script", "premium")
        self.assertEqual(result["code"], "ESTIMATE_REQUIRED")
        self.assertEqual(self.store.state("test-run")["spent"], 4)

    def test_dependencies_cannot_be_bypassed(self):
        req = validate_request(request())
        self.store.ensure_run(req)
        self.store.estimate("test-run", "premium")
        for tool in ("generate_script", "save_plan"):
            self.assertEqual(self.store.execute("test-run", tool, "premium")["code"], "DEPENDENCY_UNMET")
        self.assertEqual(self.store.state("test-run")["spent"], 0)

    def test_over_budget_action_is_rejected_before_charge(self):
        req = validate_request(request(budget=10))
        self.store.ensure_run(req)
        self.store.estimate("test-run", "premium")
        self.assertEqual(self.store.execute("test-run", "search_assets", "premium")["code"], "PLAN_NOT_FEASIBLE")
        self.assertEqual(self.store.state("test-run")["spent"], 0)

    def test_model_cannot_inject_budget_or_publish(self):
        req = validate_request(request())
        self.store.ensure_run(req)
        agent = Agent(MockModel(), self.store, self.data)
        self.assertEqual(agent.execute("test-run", Action("publish"), [])["code"], "UNKNOWN_TOOL")
        self.assertEqual(agent.execute("test-run", Action("search_assets", {"plan_id": "premium", "budget": 999}), [])["code"], "INVALID_ARGUMENTS")
        self.assertEqual(agent.execute("test-run", Action("finish"), [])["code"], "FINISH_REQUIRES_EVIDENCE")

    def test_successful_step_is_reused_under_concurrent_execution(self):
        req = validate_request(request())
        self.store.ensure_run(req)
        self.store.estimate("test-run", "premium")
        barrier = threading.Barrier(2)
        def worker(_):
            store = Store(self.path, self.data)
            try:
                barrier.wait(timeout=5)
                return store.execute("test-run", "search_assets", "premium")
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, (1, 2)))
        self.assertEqual({r["code"] for r in results}, {"SUCCEEDED", "REUSED"})
        self.assertEqual(self.store.state("test-run")["spent"], 4)
        self.assertEqual(len(self.store.snapshot("test-run")["ledger"]), 1)

    def test_sql_failure_rolls_back_plan_charge_and_step(self):
        self.run_agent(max_steps=6)  # inspect, estimate, search, estimate, generate, estimate
        before = self.store.state("test-run")
        self.store.db.execute("CREATE TRIGGER reject_plan BEFORE INSERT ON plans BEGIN SELECT RAISE(ABORT,'test'); END")
        result = self.store.execute("test-run", "save_plan", "premium")
        self.assertEqual(result["code"], "STORAGE_FAILURE")
        self.assertEqual(self.store.state("test-run"), before)
        self.assertEqual(len(self.store.snapshot("test-run")["plans"]), 0)

    def test_failed_cost_is_not_refunded_when_no_alternative_fits(self):
        result = self.run_agent(request(budget=10), fault="generate_script_always")
        self.assertLessEqual(result["actual_cost_total"], 10)
        self.assertIsNone(result["saved_plan"])
        self.assertTrue(result["uncompleted_reason"])

    def test_protocol_correction_and_fatal_errors_have_explicit_boundaries(self):
        class Recover(MockModel):
            def choose(self, req, state, history):
                if not history:
                    raise ModelProtocolError(2)
                return super().choose(req, state, history)
        result = Agent(Recover(), self.store, self.data).run(request())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["protocol_rejections"], 1)
        class Broken(MockModel):
            def choose(self, *args):
                raise ModelError("MODEL_HTTP_401")
        result = Agent(Broken(), self.store, self.data).run(request(request_id="broken"))
        self.assertEqual(result["status"], "incomplete_model_error")
        self.assertEqual(result["error"], "MODEL_HTTP_401")

    def test_invalid_inputs_and_dataset_changes(self):
        for req in (request(budget=True), request(budget=2.5), request(deadline="2026-11-05T09:00"), request(publish=True)):
            with self.subTest(req=req), self.assertRaises(ValueError):
                validate_request(req)
        changed = copy.deepcopy(self.data)
        changed["version"] = "different"
        with self.assertRaisesRegex(ValueError, "dataset changed"):
            Store(self.path, changed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
