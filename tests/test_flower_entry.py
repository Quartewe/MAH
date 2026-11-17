"""Replay the flower entrance's missed tap and homepage recovery.

On 2026-11-14 the quest match was (1148, 589, 109, 73), but its sampled
tap (1149, 602) opened the shop. After returning home the scheduler kept
waiting for map text without clicking the quest entrance again.
"""

import json
from pathlib import Path
import tempfile
import threading
import unittest

import numpy as np
from maa.controller import CustomController
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.resource import Resource
from maa.tasker import Tasker


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "assets/resource/base/pipeline/combat/flower.json"
QUEST_BOX = [1148, 589, 109, 73]
# Interior of the visible quest button, excluding the adjacent shop.
QUEST_INTERIOR = [1180, 625, 50, 55]


class FlowerController(CustomController):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def connect(self):
        return True

    def request_uuid(self):
        return "flower-entry-regression"

    def get_features(self):
        return 0

    def screencap(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def click(self, x, y):
        state = self.state
        if state["matched"] == "Flower.Go0":
            state["opens"] += 1
            state["quest_clicks"].append((x, y))
            left, top, width, height = QUEST_INTERIOR
            if not (left <= x <= left + width and top <= y <= top + height):
                state["screen"] = "shop"
            elif state["opens"] <= state["ignored_opens"]:
                state["screen"] = state["failed_screen"]
            else:
                state["screen"] = "map"
        elif state["matched"] == "Flower.Go1":
            state["screen"] = "quests"
        # Input dispatch may succeed even when the screen did not advance.
        return True


class FlowerScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        state = self.state
        box = None
        if (argv.node_name == "Flower.Go0" and state["screen"] == "home"
                and state["entry_visible"]):
            box = QUEST_BOX
        elif argv.node_name in ("Flower.Go0.1", "Flower.Go1") and state["screen"] == "map":
            box = [650, 240, 160, 38]
        if box:
            state["matched"] = argv.node_name
        return box


class FlowerAction(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        if argv.node_name == "Global.Entry":
            self.state["recoveries"] += 1
            self.state["screen"] = "home"
        elif argv.node_name.startswith("Flower.Select."):
            if self.state["screen"] != "quests":
                return False
            self.state["selected"] = argv.node_name
            self.state["screen"] = "support"
        elif argv.node_name == "Global.AutoCombat.Entry":
            self.state["ready"] = self.state["screen"] == "support"
            return self.state["ready"]
        return True


class FlowerEntryTests(unittest.TestCase):
    def replay(self, ignored_opens=0, failed_screen="home", screen="home",
               entry_visible=True, stage="ATK"):
        state = dict(screen=screen, ignored_opens=ignored_opens,
                     failed_screen=failed_screen, entry_visible=entry_visible,
                     opens=0, recoveries=0, matched=None, quest_clicks=[],
                     selected=None, ready=False)
        pipeline = json.loads(PIPELINE.read_text(encoding="utf-8"))
        interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))
        case = next(case for case in interface["option"]["choose_stage_AP"]["cases"]
                    if case.get("pipeline_override", {}).get("Flower.Go1", {}).get("next")
                    == f"Flower.Select.{stage}")
        overrides = case["pipeline_override"]
        pipeline["Flower.Go1"].update(overrides["Flower.Go1"])
        entry = overrides["Combat.Entry"]["next"]
        for name in ("Global.Entry", "Global.AutoCombat.Entry"):
            pipeline[name] = {
                "action": {"type": "Custom", "param": {"custom_action": "ReplayAction"}},
            }
        # Simulate only recognition and agent boundaries. Keep the real Click
        # targets, interface continuation and next/on_error/JumpBack/max_hit.
        for node in pipeline.values():
            if "recognition" in node:
                node["recognition"] = {
                    "type": "Custom", "param": {"custom_recognition": "ReplayScreen"},
                }
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=20, rate_limit=1)
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/flower.json").write_text(
                json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("ReplayScreen", FlowerScreen(state))
            resource.register_custom_action("ReplayAction", FlowerAction(state))
            resource.register_custom_action("QuestSelect", FlowerAction(state))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = FlowerController(state)
            self.assertTrue(controller.post_connection().wait().status.succeeded)
            tasker = Tasker()
            self.assertTrue(tasker.bind(resource, controller))
            timed_out = threading.Event()

            def stop_loop():
                timed_out.set()
                tasker.post_stop()

            watchdog = threading.Timer(2, stop_loop)
            watchdog.start()
            try:
                succeeded = tasker.post_task(entry).wait().status.succeeded
            finally:
                watchdog.cancel()
                tasker.post_stop().wait()
            self.assertFalse(timed_out.is_set(), state)
        return state, succeeded

    def test_click_area_is_inside_quest_button(self):
        node = json.loads(PIPELINE.read_text(encoding="utf-8"))["Flower.Go0"]
        x, y, width, height = node["action"].get("param", {}).get("target", QUEST_BOX)
        left, top, safe_width, safe_height = QUEST_INTERIOR
        self.assertGreaterEqual(x, left)
        self.assertGreaterEqual(y, top)
        self.assertLessEqual(x + width, left + safe_width)
        self.assertLessEqual(y + height, top + safe_height)

    def test_home_entry_reaches_selected_quest(self):
        for stage in ("ATK", "DEF"):
            with self.subTest(stage=stage):
                state, succeeded = self.replay(stage=stage)
                self.assertTrue(succeeded, state)
                self.assertTrue(state["ready"], state)
                self.assertEqual(state["selected"], f"Flower.Select.{stage}")
                self.assertEqual(state["opens"], 1)
                self.assertEqual(state["recoveries"], 0)

    def test_ignored_first_tap_is_retried(self):
        state, succeeded = self.replay(ignored_opens=1)
        self.assertTrue(succeeded, state)
        self.assertTrue(state["ready"], state)
        self.assertEqual(state["opens"], 2)

    def test_shop_after_first_tap_recovers_then_retries(self):
        state, succeeded = self.replay(ignored_opens=1, failed_screen="shop")
        self.assertTrue(succeeded, state)
        self.assertTrue(state["ready"], state)
        self.assertEqual(state["opens"], 2)
        self.assertEqual(state["recoveries"], 1)

    def test_starting_in_shop_recovers_then_enters(self):
        state, succeeded = self.replay(screen="shop")
        self.assertTrue(succeeded, state)
        self.assertTrue(state["ready"], state)
        self.assertEqual(state["opens"], 1)
        self.assertEqual(state["recoveries"], 1)

    def test_unresponsive_entrance_stops_as_failure(self):
        state, succeeded = self.replay(ignored_opens=100)
        self.assertFalse(succeeded, state)
        self.assertFalse(state["ready"], state)
        self.assertGreaterEqual(state["opens"], 2)
        self.assertLessEqual(state["opens"], 3)

    def test_missing_entrance_stops_as_failure(self):
        state, succeeded = self.replay(entry_visible=False)
        self.assertFalse(succeeded, state)
        self.assertFalse(state["ready"], state)
        self.assertEqual(state["opens"], 0)
        self.assertLessEqual(state["recoveries"], 2)


if __name__ == "__main__":
    unittest.main()
