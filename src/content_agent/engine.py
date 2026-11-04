from dataclasses import asdict
from datetime import timedelta
import copy
from .domain import DEPENDENCIES, ORDER, digest, missing, timestamp, validate_request
from .models import ModelError, ModelProtocolError, TOOLS


def outcome(state, history):
    if state["saved_plan"]:
        return "completed"
    if missing(state["request"]):
        return "needs_info"
    last = state["last_estimate"]
    if last and last["revision"] == state["revision"] and not last["feasible"]:
        return "constraints_infeasible"
    if state["last_error"]:
        return "needs_materials" if state["last_error"]["code"] == "NO_ASSETS" else "tool_failed"
    if any(e.get("observation", {}).get("code") == "STORAGE_FAILURE" for e in history):
        return "tool_failed"
    return "incomplete"


class Agent:
    def __init__(self, model, store, data, max_steps=40, fault=None):
        if not 1 <= max_steps <= 100:
            raise ValueError("max_steps must be 1..100")
        self.model, self.store, self.data = model, store, data
        self.max_steps, self.fault = max_steps, fault

    def execute(self, run_id, action, history):
        name, args = action.tool, action.arguments
        if name not in TOOLS or not isinstance(args, dict):
            return {"ok": False, "code": "UNKNOWN_TOOL"}
        expected = set() if name in {"inspect_run", "finish"} else {"plan_id"}
        if set(args) != expected or (expected and args["plan_id"] not in ("premium", "lean")):
            return {"ok": False, "code": "INVALID_ARGUMENTS"}
        if name == "inspect_run":
            return self.store.inspect(run_id)
        if name == "estimate_plan":
            return self.store.estimate(run_id, args["plan_id"])
        if name == "finish":
            status = outcome(self.store.state(run_id), history)
            return {"ok": status != "incomplete", "code": "FINISHED" if status != "incomplete" else "FINISH_REQUIRES_EVIDENCE",
                    "status": status, "reason": "Finish reflects persisted evidence; a feasible unfinished plan still needs execution."}
        return self.store.execute(run_id, name, args["plan_id"], self.fault)

    def run(self, raw):
        req = validate_request(raw)
        run_id = req["request_id"]
        self.store.ensure_run(req)
        starting = self.store.state(run_id)
        history, stop, error = [], "step_limit", None
        for number in range(1, self.max_steps + 1):
            state = {**self.store.state(run_id), "run_id": run_id}
            try:
                action = self.model.choose(req, copy.deepcopy(state), copy.deepcopy(history))
            except ModelProtocolError as exc:
                error = str(exc)
                history.append({"step": number, "run_id": run_id, "model_error": error,
                                "recoverable": True, "diagnostics": exc.diagnostics})
                continue
            except ModelError as exc:
                error, stop = str(exc), "model_error"
                history.append({"step": number, "run_id": run_id, "model_error": error})
                break
            error = None
            observation = self.execute(run_id, action, history)
            history.append({"step": number, "run_id": run_id, "action": asdict(action),
                            "observation": copy.deepcopy(observation)})
            if action.tool == "finish" and observation["ok"]:
                stop = "finished"
                break
        state = self.store.state(run_id)
        status = outcome(state, history) if stop == "finished" else "incomplete_" + stop
        for index, event in enumerate(history):
            event["next_action"] = (history[index + 1].get("action", {}).get("tool", "model_error")
                                    if index + 1 < len(history) else "stop")
        selected = (state["saved_plan"]["variant"] if state["saved_plan"] else
                    state["last_estimate"]["plan_id"] if state["last_estimate"] else None)
        pending_time = timestamp(state["effective_start"]) + timedelta(minutes=state["elapsed_minutes"])
        task_plan = []
        for name in ORDER:
            step = state["steps"].get(name)
            fee = self.data["plans"][selected]["steps"][name] if selected else None
            task_plan.append({"tool": name, "dependencies": DEPENDENCIES[name],
                              "status": step["status"] if step else "pending",
                              "step_id": step["id"] if step else None,
                              "result": step["output"] if step else None,
                              "attempt_count": step["attempt_count"] if step else 0,
                              "remaining_estimated_cost": 0 if step and step["status"] == "succeeded" else fee["cost"] if fee else None,
                              "remaining_estimated_minutes": 0 if step and step["status"] == "succeeded" else fee["minutes"] if fee else None})
        return {"schema_version": "1.0", "mode": self.model.mode, "model": self.model.name,
                "request": req, "dataset_sha256": digest(self.data), "status": status,
                "stop_reason": stop, "error": error,
                "uncompleted_reason": None if status == "completed" else {
                    "status": status, "missing_fields": missing(req), "last_tool_error": state["last_error"],
                    "constraint_gaps": [{"plan_id": e["plan_id"], "budget_gap": e["budget_gap"],
                        "deadline_gap_minutes": e["deadline_gap_minutes"]} for e in state["estimates"]
                        if e["revision"] == state["revision"] and not e["feasible"]], "model_error": error},
                "missing_fields": missing(req), "selected_plan": selected, "task_plan": task_plan,
                "actual_cost_total": state["spent"], "charged_this_invocation": state["spent"] - starting["spent"],
                "business_attempts_this_invocation": len(state["attempts"]) - len(starting["attempts"]),
                "elapsed_business_minutes": state["elapsed_minutes"], "business_clock": pending_time.isoformat(timespec="minutes"),
                "estimates": state["estimates"], "latest_estimate": state["last_estimate"],
                "attempts": state["attempts"], "saved_plan": state["saved_plan"],
                "plan_save_status": "saved" if state["saved_plan"] else "not_saved",
                "max_steps": self.max_steps, "model_calls": len(history),
                "tool_calls": sum("action" in e for e in history),
                "protocol_rejections": sum(e.get("recoverable", False) for e in history),
                "trace": history, "published": False,
                "boundary": "Simulated business costs/time and local tools. Mock is workflow-only; live mode uses real model decisions."}
