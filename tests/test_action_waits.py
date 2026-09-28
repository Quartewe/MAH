"""Replay production run_action calls in MaaFramework with a device-free controller."""

import ast
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from maa.custom_action import CustomAction
from maa.resource import Resource
from maa.tasker import Tasker

from test_activity_entry import ROOT, ScreenController


def action_calls(path, entry):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return sorted((node for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == "run_action" and node.args
                   and isinstance(node.args[0], ast.Constant) and node.args[0].value == entry),
                  key=lambda node: node.lineno)


class WaitController(ScreenController):
    def __init__(self):
        super().__init__()
        self.captures = 0
        self.captures_before_action = 0

    def screencap(self):
        self.captures += 1
        return super().screencap()

    def click(self, x, y):
        self.captures_before_action = self.captures
        return True

    def swipe(self, x1, y1, x2, y2, duration):
        self.captures_before_action = self.captures
        return True

    def touch_down(self, contact, x, y, pressure):
        self.captures_before_action = self.captures
        return True

    def touch_move(self, contact, x, y, pressure):
        return True

    def touch_up(self, contact):
        return True


class RunCall(CustomAction):
    def __init__(self, call, controller):
        super().__init__()
        self.code = compile(ast.Expression(call), "production-run-action", "eval")
        self.controller = controller

    def run(self, context, argv):
        self.controller.captures = 0
        result = eval(self.code, {"context": context, "back_res": SimpleNamespace(
            best_result=SimpleNamespace(box=[32, 45, 64, 36]))})
        return result is not None and result.success


class ActionWaitTests(unittest.TestCase):
    def replay(self, filename, entry):
        call = action_calls(ROOT / "agent/custom/action" / filename, entry)[0]
        source = json.loads((ROOT / "assets/resource/base/pipeline/Utils.json").read_text(encoding="utf-8"))
        node = source[entry]
        # Only scale duration; retain production target and actual call arguments.
        wait = node["pre_wait_freezes"]
        wait = dict(wait) if isinstance(wait, dict) else {"time": wait}
        wait.update(time=10, rate_limit=1, timeout=500)
        node.update(pre_wait_freezes=wait, pre_delay=0, post_delay=0, duration=1, end_hold=0)
        pipeline = {entry: node, "Replay": {
            "pre_delay": 0, "post_delay": 0,
            "action": {"type": "Custom", "param": {"custom_action": "RunCall"}},
        }}
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/test.json").write_text(json.dumps(pipeline), encoding="utf-8")
            controller = WaitController()
            resource = Resource()
            resource.register_custom_action("RunCall", RunCall(call, controller))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            self.assertTrue(controller.post_connection().wait().status.succeeded)
            tasker = Tasker()
            self.assertTrue(tasker.bind(resource, controller))
            self.assertTrue(tasker.post_task("Replay").wait().status.succeeded)
            self.assertGreaterEqual(controller.captures_before_action, 2,
                                    "Stable-image wait was skipped before the action")

    def test_return_click_waits_on_button(self):
        self.replay("go_back.py", "UtilsClick")

    def test_team_swipe_waits_on_list(self):
        self.replay("team_select.py", "UtilsSwipe")

    def test_all_shared_action_callers_supply_a_wait_region(self):
        # Catch omissions in other consumers of the same shared default (target=true).
        for path in (ROOT / "agent").rglob("*.py"):
            for entry in ("UtilsClick", "UtilsSwipe"):
                for call in action_calls(path, entry):
                    keywords = {kw.arg: kw.value for kw in call.keywords}
                    has_box = len(call.args) > 1 or "box" in keywords
                    override = keywords.get("pipeline_override")
                    has_target = False
                    if override is not None:
                        for node in ast.walk(override):
                            if not isinstance(node, ast.Dict):
                                continue
                            for key, value in zip(node.keys, node.values):
                                if isinstance(key, ast.Constant) and key.value == "pre_wait_freezes" and isinstance(value, ast.Dict):
                                    has_target = any(isinstance(k, ast.Constant) and k.value == "target" for k in value.keys)
                    with self.subTest(path=str(path.relative_to(ROOT)), line=call.lineno):
                        self.assertTrue(has_box or has_target, "No box or explicit pre_wait_freezes.target")


if __name__ == "__main__":
    unittest.main()
