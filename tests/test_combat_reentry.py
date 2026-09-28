"""Exercise re-entry timing with the real pipeline scheduler and a fake screen.

On 2026-09-27 at 11:51:14, Drink1 succeeded; at 11:51:54 its
next-list timed out. MENU was visible by 11:52:00, but Back0 was already
looking for exit buttons. Scale the production timeouts by 100 so this
late-arriving battle can be reproduced without a device in under a second.
"""

import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.resource import Resource
from maa.tasker import Tasker

from test_activity_entry import ROOT, ScreenController


PREFIX = "Global.AutoCombat"


class CombatScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        if self.state["screen"] == "loading" and time.monotonic() >= self.state["ready_at"]:
            self.state["screen"] = "battle"
        expected = {
            PREFIX: "battle",
            PREFIX + ".Replay": "results",
            PREFIX + ".Drink1": "drink",
            PREFIX + ".Replay1": "confirmation",
            PREFIX + ".Wait": "loading",
        }.get(argv.node_name)
        if argv.node_name == PREFIX + ".Wait" and not self.state["loading_label"]:
            return None
        if self.state["screen"] == expected:
            return [25, 15, 87, 35]
        return None


class CombatAction(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        self.state["visited"].append(argv.node_name)
        if argv.node_name.endswith(".Drink1") and not self.state["drink_success"]:
            return False
        if argv.node_name == PREFIX + ".Replay" and self.state["needs_drink"]:
            self.state["screen"] = "drink"
        elif argv.node_name in (PREFIX + ".Replay", PREFIX + ".Drink1"):
            self.state["screen"] = "loading"
            self.state["ready_at"] = time.monotonic() + self.state["loading_seconds"]
        elif argv.node_name == PREFIX:
            self.state["resumed"] = True
        elif argv.node_name == PREFIX + ".Back0":
            self.state["exited"] = True
        return True


class CombatReentryTests(unittest.TestCase):
    def replay(self, entry, loading_seconds=0.4, drink_success=True,
               loading_label=True, needs_drink=False):
        initial_screen = "results" if entry == PREFIX + ".Replay" else "drink"
        state = dict(screen=initial_screen, ready_at=float("inf"),
                     loading_seconds=loading_seconds, drink_success=drink_success,
                     loading_label=loading_label, needs_drink=needs_drink,
                     resumed=False, exited=False, visited=[])
        pipeline = json.loads((ROOT / "assets/resource/base/pipeline/combat/global_combat.json")
                              .read_text(encoding="utf-8"))
        pipeline["Global.GoBackToHomePage"] = {}
        for name, node in pipeline.items():
            # Retain the real routing and relative timeout budgets. Recognition
            # supplies only the expected screen; no test runs a real battle.
            node.update(timeout=max(1, node.get("timeout", 20000) // 100),
                        rate_limit=10, pre_delay=0, post_delay=0,
                        pre_wait_freezes=0, post_wait_freezes=0)
            recognition = node.get("recognition", "DirectHit")
            kind = recognition.get("type") if isinstance(recognition, dict) else recognition
            if kind != "DirectHit":
                node["recognition"] = {
                    "type": "Custom", "param": {"custom_recognition": "CombatScreen"}
                }
            node["action"] = {
                "type": "Custom", "param": {"custom_action": "CombatAction"}
            }
        # Stop at the two meaningful outcomes instead of fighting/exiting.
        for name in (PREFIX, PREFIX + ".Back0"):
            pipeline[name]["next"] = []
            pipeline[name]["on_error"] = []

        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/combat.json").write_text(json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("CombatScreen", CombatScreen(state))
            resource.register_custom_action("CombatAction", CombatAction(state))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = ScreenController()
            self.assertTrue(controller.post_connection().wait().status.succeeded)
            tasker = Tasker()
            self.assertTrue(tasker.bind(resource, controller))
            timed_out = threading.Event()

            def stop_loop():
                timed_out.set()
                tasker.post_stop()

            watchdog = threading.Timer(5, stop_loop)
            watchdog.start()
            try:
                succeeded = tasker.post_task(entry).wait().status.succeeded
            finally:
                watchdog.cancel()
            self.assertFalse(timed_out.is_set(), state["visited"][:20])
        return state, succeeded

    def test_slow_loading_after_drink_resumes_battle(self):
        state, succeeded = self.replay(PREFIX + ".Drink1")
        self.assertTrue(state["resumed"], state["visited"])
        self.assertFalse(state["exited"])
        self.assertTrue(succeeded)

    def test_regular_replay_still_resumes_battle(self):
        state, succeeded = self.replay(PREFIX + ".Replay")
        self.assertTrue(state["resumed"], state["visited"])
        self.assertTrue(succeeded)

    def test_fast_loading_after_drink_still_resumes(self):
        state, succeeded = self.replay(PREFIX + ".Drink1", loading_seconds=0)
        self.assertTrue(state["resumed"], state["visited"])
        self.assertTrue(succeeded)

    def test_loading_without_loading_text_still_resumes(self):
        state, succeeded = self.replay(PREFIX + ".Replay", loading_label=False)
        self.assertTrue(state["resumed"], state["visited"])
        self.assertTrue(succeeded)

    def test_replay_handles_potion_prompt_then_slow_loading(self):
        state, succeeded = self.replay(PREFIX + ".Replay", needs_drink=True)
        self.assertTrue(state["resumed"], state["visited"])
        self.assertFalse(state["exited"])
        self.assertEqual(state["visited"].count(PREFIX + ".Drink1"), 1)
        self.assertTrue(succeeded)

    def test_failed_drink_still_exits(self):
        state, succeeded = self.replay(PREFIX + ".Drink1", drink_success=False)
        self.assertFalse(state["resumed"])
        self.assertTrue(state["exited"], state["visited"])
        self.assertTrue(succeeded)

    def test_permanent_loading_reports_failure(self):
        state, succeeded = self.replay(PREFIX + ".Drink1", loading_seconds=float("inf"))
        self.assertFalse(state["resumed"])
        self.assertFalse(state["exited"], state["visited"])
        self.assertFalse(succeeded, state["visited"])


if __name__ == "__main__":
    unittest.main()
