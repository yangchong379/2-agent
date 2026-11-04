import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from content_agent.domain import validate_request
from content_agent.models import ChatModel, ModelError, ModelProtocolError
from connect_deepseek import connect, read_secret, retry_plan, next_destination


def request():
    return validate_request({"request_id": "interface-test", "topic": "夏日旅行", "budget": 15,
                             "start_at": "2026-11-05T09:00+08:00", "deadline": "2026-11-05T11:30+08:00"})


class Response:
    def __init__(self, message):
        self.message = message
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return json.dumps({"choices": [{"message": self.message}]}).encode()


def message(name="inspect_run", call_id="provider-call"):
    return {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {
        "name": name, "arguments": '{"rationale":"Read persistent execution state."}'}}]}


class AdapterTests(unittest.TestCase):
    def adapter(self, current):
        class Opener:
            def __init__(self):
                self.requests = []
            def open(self, req, timeout):
                self.requests.append(json.loads(req.data))
                return Response(current)
        self.opener = Opener()
        return ChatModel("https://example.invalid/v1", "test-model", "fake-test-secret", opener=self.opener)

    def test_actual_observation_and_original_call_id_are_replayed(self):
        current = message()
        current["reasoning_content"] = "PRIVATE-REASONING"
        model = self.adapter(current)
        state = {"run_id": "interface-test"}
        action = model.choose(request(), state, [])
        history = [{"action": {"tool": action.tool, "arguments": action.arguments, "rationale": action.rationale},
                    "observation": {"ok": True, "state": {"spent": 7}}}]
        model.choose(request(), state, history)
        messages = self.opener.requests[-1]["messages"]
        self.assertEqual(messages[-1]["tool_call_id"], "provider-call")
        self.assertEqual(json.loads(messages[-1]["content"])["state"]["spent"], 7)
        self.assertEqual(messages[-2]["reasoning_content"], "PRIVATE-REASONING")
        self.assertNotIn("PRIVATE-REASONING", json.dumps(history))

    def test_non_thinking_mode_requires_a_model_tool_choice(self):
        model = self.adapter(message())
        with patch.dict(os.environ, {"MODEL_THINKING": "disabled"}):
            model.choose(request(), {"run_id": "interface-test"}, [])
        self.assertEqual(self.opener.requests[-1]["tool_choice"], "required")

    def test_multi_call_rejection_returns_no_execution_results_for_each_call(self):
        current = message()
        current["tool_calls"].append(message(call_id="second-call")["tool_calls"][0])
        model = self.adapter(current)
        with self.assertRaises(ModelProtocolError) as failure:
            model.choose(request(), {"run_id": "interface-test"}, [])
        self.assertEqual(failure.exception.diagnostics["tool_calls_count"], 2)
        current["tool_calls"] = [message(call_id="corrected")["tool_calls"][0]]
        model.choose(request(), {"run_id": "interface-test"}, [{"recoverable": True, "model_error": str(failure.exception)}])
        replies = [m for m in self.opener.requests[-1]["messages"] if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in replies], ["provider-call", "second-call"])
        self.assertTrue(all(json.loads(m["content"])["executed"] is False for m in replies))

    def test_error_does_not_expose_provider_body(self):
        model = self.adapter(message())
        self.opener.open = lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError("https://example.invalid", 401, "PRIVATE-BODY", {}, None))
        with self.assertRaisesRegex(ModelError, "^MODEL_HTTP_401$"):
            model.choose(request(), {"run_id": "interface-test"}, [])

    def test_missing_credentials_and_unsafe_urls_are_rejected(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            ChatModel()
        with self.assertRaises(ValueError):
            ChatModel("https://user:password@example.invalid", "model", "fake")


class HelperTests(unittest.TestCase):
    def test_local_secret_is_not_printed_and_environment_is_restored(self):
        def runner(args):
            self.assertEqual(os.environ["MODEL_API_KEY"], "fake-test-secret")
            self.assertIn("live", args)
            return 0
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            self.assertEqual(connect(secret_reader=lambda prompt: "fake-test-secret", runner=runner), 0)
            self.assertNotIn("MODEL_API_KEY", os.environ)
        self.assertNotIn("fake-test-secret", output.getvalue())

    def test_latest_successful_retry_does_not_request_a_new_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder, stamp, passed in (("live", "2026-11-04T09:00:00+00:00", False),
                                          ("live-retry", "2026-11-04T10:00:00+00:00", True)):
                path = root / "examples/runs" / folder
                path.mkdir(parents=True)
                (path / "summary.json").write_text(json.dumps({"mode": "live_model", "generated_at_utc": stamp,
                    "cases": [{"case": "normal", "passed": passed}]}), encoding="utf-8")
            reader = MagicMock()
            with patch("connect_deepseek.ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(retry_plan(), [])
                self.assertEqual(connect(retry=True, secret_reader=reader), 0)
            reader.assert_not_called()

    def test_new_evaluation_directory_preserves_previous_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "examples/runs/live").mkdir(parents=True)
            with patch("connect_deepseek.ROOT", root):
                self.assertEqual(next_destination("live").name, "live-2")

    def test_windows_dialog_masks_input(self):
        tk = MagicMock()
        tk.TclError = RuntimeError
        tk.simpledialog.askstring.return_value = "fake-test-secret"
        with patch("connect_deepseek.sys.platform", "win32"), patch.dict(sys.modules, {"tkinter": tk, "tkinter.simpledialog": tk.simpledialog}):
            self.assertEqual(read_secret("prompt"), "fake-test-secret")
        self.assertEqual(tk.simpledialog.askstring.call_args.kwargs["show"], "*")
        tk.Tk.return_value.destroy.assert_called_once()


class CliTests(unittest.TestCase):
    def test_cli_exit_codes_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            for name, change, flags, expected in (("normal", {}, [], 0), ("missing", {"budget": None}, [], 2),
                                                   ("limit", {}, ["--max-steps", "2"], 3), ("invalid", {"budget": True}, [], 4)):
                folder = Path(temp) / name
                folder.mkdir()
                req = {**request(), **change}
                (folder / "input.json").write_text(json.dumps(req), encoding="utf-8")
                result = subprocess.run([sys.executable, str(ROOT / "scripts/run.py"), "--input", str(folder / "input.json"),
                    "--data", str(ROOT / "data/fixtures.json"), "--db", str(folder / "planner.sqlite"),
                    "--output", str(folder / "result.json"), *flags], cwd=ROOT, capture_output=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual((folder / "result.json").exists(), expected != 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
