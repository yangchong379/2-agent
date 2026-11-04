"""Transactions keep outputs, simulated fees and business time in the same commit."""
from datetime import timedelta
import json
import sqlite3
from .domain import DEPENDENCIES, ORDER, canonical, digest, estimate, initial_state, missing, timestamp


class Store:
    def __init__(self, path, data):
        self.data = data
        self.db = sqlite3.connect(str(path), timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,tool TEXT NOT NULL,
          plan_id TEXT NOT NULL,status TEXT NOT NULL,cost INTEGER NOT NULL,minutes INTEGER NOT NULL,code TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,run_id TEXT NOT NULL UNIQUE,content TEXT NOT NULL);
        """)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()
            if row and row[0] != digest(data):
                raise ValueError("dataset changed; use a separate database to keep existing evidence intact")
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES('dataset',?)", (digest(data),))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            self.close()
            raise

    def close(self):
        self.db.close()

    def ensure_run(self, req):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT fingerprint FROM runs WHERE id=?", (req["request_id"],)).fetchone()
            if row and row[0] != digest(req):
                raise ValueError("REQUEST_ID_REUSED: changed topic, budget or deadline requires a new request_id")
            self.db.execute("INSERT OR IGNORE INTO runs VALUES(?,?,?)",
                            (req["request_id"], digest(req), canonical(initial_state(req))))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def state(self, run_id):
        row = self.db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise ValueError("unknown run")
        return json.loads(row[0])

    def _write(self, run_id, state):
        self.db.execute("UPDATE runs SET state=? WHERE id=?", (canonical(state), run_id))

    def inspect(self, run_id):
        state = self.state(run_id)
        return {"ok": True, "state": state, "missing_fields": missing(state["request"]),
                "plans": self.data["plans"], "failure_fees": self.data["failure_fees"],
                "boundary": "Costs and elapsed business minutes are simulated; API token charges and network latency are excluded."}

    def estimate(self, run_id, plan_id):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            state = self.state(run_id)
            result = estimate(state, self.data, plan_id)
            if result["ok"]:
                state["last_estimate"] = result
                state["estimates"].append(result)
                self._write(run_id, state)
            self.db.execute("COMMIT")
            return result
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def execute(self, run_id, tool, plan_id, fault=None):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            state = self.state(run_id)
            req = state["request"]
            if plan_id not in self.data["plans"]:
                return self._reject("UNKNOWN_PLAN")
            if missing(req):
                return self._reject("MISSING_INPUT", missing_fields=missing(req))
            old = state["steps"].get(tool)
            if old and old["status"] == "succeeded":
                if tool != "search_assets" and old["plan_id"] != plan_id:
                    return self._reject("SUCCESSFUL_STEP_PLAN_LOCKED", actual_plan_id=old["plan_id"])
                self.db.execute("COMMIT")
                return {"ok": True, "code": "REUSED", "step": old, "charged_now": 0,
                        "spent_total": state["spent"], "note": "Successful output retained; not re-executed or charged again."}
            unmet = [name for name in DEPENDENCIES[tool] if state["steps"].get(name, {}).get("status") != "succeeded"]
            if unmet:
                return self._reject("DEPENDENCY_UNMET", missing_steps=unmet)
            observed = state["last_estimate"]
            if not observed or observed["plan_id"] != plan_id or observed["revision"] != state["revision"]:
                return self._reject("ESTIMATE_REQUIRED", revision=state["revision"], reason="Estimate this plan after each charged attempt; successful steps are excluded from remaining cost.")
            current = estimate(state, self.data, plan_id)
            if not current["ok"] or not current["feasible"]:
                return self._reject("PLAN_NOT_FEASIBLE", estimate=current)
            failed_before = any(a["tool"] == tool and a["status"] == "failed" for a in state["attempts"])
            inject = fault in {tool + "_always", tool + "_once"} and (fault.endswith("_always") or not failed_before)
            fee = self.data["failure_fees"][tool] if inject else self.data["plans"][plan_id]["steps"][tool]
            end = timestamp(state["effective_start"]) + timedelta(minutes=state["elapsed_minutes"] + fee["minutes"])
            if state["spent"] + fee["cost"] > req["budget"] or end > timestamp(req["deadline"]):
                return self._reject("HARD_LIMIT_EXCEEDED", projected_charge=fee["cost"], projected_end=end.isoformat(timespec="minutes"))
            code = "TOOL_FAILURE" if inject else "SUCCEEDED"
            output = None
            if not inject and tool == "search_assets":
                assets = [m for m in self.data["materials"] if m["topic"] == req["topic"] and m["tier"] == plan_id]
                if not assets:
                    code = "NO_ASSETS"
                else:
                    output = {"materials": assets}
            if not inject and tool == "generate_script":
                assets = state["steps"]["search_assets"]["output"]["materials"]
                output = {"title": req["topic"] + "内容活动", "asset_ids": [m["id"] for m in assets],
                          "script": f"围绕{req['topic']}：开场引出主题；结合授权合成素材展示三个内容亮点；结尾引导用户参与。",
                          "style": self.data["plans"][plan_id]["name"], "synthetic": True}
            attempt_id = "attempt-" + digest([run_id, len(state["attempts"]) + 1])[:20]
            succeeded = code == "SUCCEEDED"
            state["spent"] += fee["cost"]
            state["elapsed_minutes"] += fee["minutes"]
            state["revision"] += 1
            attempt = {"id": attempt_id, "tool": tool, "plan_id": plan_id,
                       "status": "succeeded" if succeeded else "failed", "code": code,
                       "cost": fee["cost"], "minutes": fee["minutes"]}
            state["attempts"].append(attempt)
            step_id = "step-" + digest([run_id, tool])[:20]
            if succeeded and tool == "save_plan":
                plan_id_saved = "plan-" + digest(run_id)[:20]
                document = {"id": plan_id_saved, "topic": req["topic"], "variant": plan_id,
                            "budget": req["budget"], "deadline": req["deadline"], "total_cost": state["spent"],
                            "finish_at": end.isoformat(timespec="minutes"),
                            "materials": state["steps"]["search_assets"]["output"],
                            "script": state["steps"]["generate_script"]["output"],
                            "completed_steps": list(ORDER), "published": False}
                self.db.execute("INSERT INTO plans VALUES(?,?,?)", (plan_id_saved, run_id, canonical(document)))
                state["saved_plan"] = document
                output = {"plan_id": plan_id_saved, "saved": True}
            state["steps"][tool] = {"id": step_id, "status": attempt["status"], "plan_id": plan_id,
                                    "dependencies": DEPENDENCIES[tool], "output": output,
                                    "last_attempt_id": attempt_id,
                                    "attempt_count": sum(a["tool"] == tool for a in state["attempts"])}
            state["last_error"] = None if succeeded else {"tool": tool, "code": code}
            self.db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?)", (
                attempt_id, run_id, tool, plan_id, attempt["status"], fee["cost"], fee["minutes"], code))
            self._write(run_id, state)
            self.db.execute("COMMIT")
            return {"ok": succeeded, "code": code, "step": state["steps"][tool], "charged_now": fee["cost"],
                    "spent_total": state["spent"], "elapsed_minutes": state["elapsed_minutes"],
                    "estimate_required": True, "revision": state["revision"],
                    "note": "Completed dependencies are retained; changing plan does not refund earlier costs."}
        except sqlite3.Error:
            try:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            return {"ok": False, "code": "STORAGE_FAILURE", "charged_now": 0}

    def _reject(self, code, **details):
        self.db.execute("ROLLBACK")
        return {"ok": False, "code": code, "charged_now": 0, **details}

    def snapshot(self, run_id):
        return {"state": self.state(run_id),
                "plans": [dict(r) for r in self.db.execute("SELECT * FROM plans WHERE run_id=?", (run_id,))],
                "ledger": [dict(r) for r in self.db.execute("SELECT * FROM attempts WHERE run_id=? ORDER BY rowid", (run_id,))]}
