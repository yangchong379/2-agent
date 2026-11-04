import argparse
import json
from pathlib import Path
import sqlite3
import sys
from .engine import Agent
from .models import ChatModel, MockModel
from .store import Store


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stateful content planning; synthetic costs and time, no publication")
    parser.add_argument("--input", required=True)
    parser.add_argument("--data", default="data/fixtures.json")
    parser.add_argument("--db", default=".runtime/planner.sqlite")
    parser.add_argument("--output", default=".runtime/result.json")
    parser.add_argument("--model", choices=["mock", "live"], default="mock")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--fault", choices=["search_assets_once", "search_assets_always", "generate_script_once", "generate_script_always", "save_plan_once", "save_plan_always"])
    args = parser.parse_args(argv)
    store = None
    try:
        req, data = read_json(args.input), read_json(args.data)
        model = MockModel() if args.model == "mock" else ChatModel()
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
        store = Store(args.db, data)
        result = Agent(model, store, data, args.max_steps, args.fault).run(req)
        write_json(args.output, result)
        print(json.dumps({"output": args.output, "mode": result["mode"], "status": result["status"],
                          "actual_cost_total": result["actual_cost_total"],
                          "charged_this_invocation": result["charged_this_invocation"],
                          "plan_save_status": result["plan_save_status"]}, ensure_ascii=False))
        return 0 if result["status"] == "completed" else 3 if result["status"].startswith("incomplete_") else 2
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 4
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
