from datetime import datetime, timedelta, timezone
import hashlib
import json

TZ = timezone(timedelta(hours=8))
ORDER = ("search_assets", "generate_script", "save_plan")
DEPENDENCIES = {"search_assets": [], "generate_script": ["search_assets"], "save_plan": ["generate_script"]}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("time must be an ISO 8601 string")
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timedelta(hours=8) or result.second or result.microsecond:
        raise ValueError("time requires explicit +08:00 and minute precision")
    return result


def validate_request(raw):
    if not isinstance(raw, dict) or set(raw) - {"request_id", "topic", "budget", "deadline", "start_at"}:
        raise ValueError("unknown request fields or non-object request")
    req = {"request_id": raw.get("request_id"), "topic": raw.get("topic", ""),
           "budget": raw.get("budget"), "deadline": raw.get("deadline"), "start_at": raw.get("start_at")}
    if not isinstance(req["request_id"], str) or not 1 <= len(req["request_id"]) <= 100:
        raise ValueError("request_id must be a nonempty string of at most 100 characters")
    if not isinstance(req["topic"], str) or len(req["topic"]) > 200:
        raise ValueError("topic must be a string of at most 200 characters")
    req["topic"] = req["topic"].strip()
    if req["budget"] is not None and (type(req["budget"]) is not int or not 0 <= req["budget"] <= 100000):
        raise ValueError("budget must be a nonnegative integer in simulated units")
    for field in ("deadline", "start_at"):
        if req[field] is not None:
            req[field] = timestamp(req[field]).isoformat(timespec="minutes")
    return req


def missing(req):
    return [field for field in ("topic", "budget", "deadline")
            if req.get(field) is None or req.get(field) == ""]


def initial_state(req):
    start = req["start_at"] or datetime.now(TZ).replace(second=0, microsecond=0).isoformat(timespec="minutes")
    return {"request": req, "effective_start": start, "spent": 0, "elapsed_minutes": 0,
            "revision": 0, "steps": {}, "attempts": [], "estimates": [],
            "last_estimate": None, "last_error": None, "saved_plan": None}


def estimate(state, data, plan_id):
    req = state["request"]
    unavailable = missing(req)
    if unavailable:
        return {"ok": False, "code": "MISSING_INPUT", "missing_fields": unavailable}
    if plan_id not in data["plans"]:
        return {"ok": False, "code": "UNKNOWN_PLAN"}
    script = state["steps"].get("generate_script", {})
    if script.get("status") == "succeeded" and script["plan_id"] != plan_id:
        return {"ok": False, "code": "SUCCESSFUL_SCRIPT_PLAN_LOCKED", "plan_id": script["plan_id"]}
    fees = data["plans"][plan_id]["steps"]
    todo = [name for name in ORDER if state["steps"].get(name, {}).get("status") != "succeeded"]
    remaining_cost = sum(fees[name]["cost"] for name in todo)
    remaining_minutes = sum(fees[name]["minutes"] for name in todo)
    projected = state["spent"] + remaining_cost
    end = timestamp(state["effective_start"]) + timedelta(minutes=state["elapsed_minutes"] + remaining_minutes)
    budget_gap = max(0, projected - req["budget"])
    time_gap = max(0, int((end - timestamp(req["deadline"])).total_seconds() // 60))
    return {"ok": True, "plan_id": plan_id, "revision": state["revision"],
            "base_plan_cost": sum(fees[name]["cost"] for name in ORDER),
            "spent_so_far": state["spent"], "remaining_cost": remaining_cost,
            "projected_total_cost": projected, "remaining_minutes": remaining_minutes,
            "projected_finish": end.isoformat(timespec="minutes"), "budget_gap": budget_gap,
            "deadline_gap_minutes": time_gap, "feasible": budget_gap == time_gap == 0,
            "remaining_steps": todo}
