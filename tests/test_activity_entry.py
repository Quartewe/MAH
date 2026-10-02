"""Replay the activity-entry failure through MaaFramework without a device.

The 2026-09-27 trace entered Activity.Select after a dungeon, saw only map
labels instead of the requested quests, and reported task success after
returning home. A subsequent run with the same quest parameters worked.

On 2026-10-02 at 16:00:26, returning from a first-clear bonus reopened
Activity.Go on the quest list. Its OCR clicked the card's "活动（自由）"
label, opening a stamina prompt before QuestSelect was ready to run.
"""

import json
from pathlib import Path
import re
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


class ScreenController(CustomController):
    def connect(self):
        return True

    def request_uuid(self):
        return "activity-entry-regression"

    def screencap(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class ActivityScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        if self.state["screen"] == "home" and self.state["entry_visible"]:
            return [561, 658, 139, 20]
        # The first-clear return leaves a quest card in the home-entry ROI.
        # This is the OCR text and box captured on 2026-10-02 at 16:00:26.
        if self.state["screen"] == "quests" and any(
            re.search(pattern, "活动（自由）") for pattern in self.state["entry_patterns"]
        ):
            return [596, 606, 84, 19]
        return None


class ActivityAction(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        self.state["visited"].append(argv.node_name)
        if argv.node_name == "Activity.Go":
            if self.state["screen"] == "quests":
                self.state["wrong_quest_clicks"] += 1
                self.state["screen"] = "drink"
                return True
            self.state["opens"] += 1
            self.state["screen"] = (
                "quests" if self.state["opens"] > self.state["failed_opens"]
                else "map"
            )
        elif argv.node_name == "Activity.Select":
            return self.state["screen"] == "quests"
        elif argv.node_name == "Global.Entry":
            self.state["screen"] = "home"
        elif argv.node_name == "Global.AutoCombat.Entry":
            self.state["started_combat"] = True
        return True


class ActivityEntryTests(unittest.TestCase):
    def replay(self, failed_opens, screen="home", entry_visible=True,
               first_clear_return=False):
        state = dict(screen=screen, opens=0, failed_opens=failed_opens,
                     entry_visible=entry_visible, started_combat=False, visited=[],
                     wrong_quest_clicks=0)
        pipeline = json.loads((ROOT / "assets/resource/base/pipeline/combat/activity.json")
                              .read_text(encoding="utf-8"))
        state["entry_patterns"] = pipeline["Activity.Go"]["recognition"]["param"]["expected"]
        entry = "Activity.Entry"
        if first_clear_return:
            # Use the interface producer's real return target, not a duplicate
            # route invented by this test. The reward page has just closed.
            interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))
            entry = "Global.AutoCombat.BacktoEntry"
            pipeline[entry] = interface["option"]["custom_stage_Activity"]["pipeline_override"][entry]
        # Stub only device/agent boundaries; run the production next/on_error,
        # JumpBack and max_hit logic in the real MaaFramework scheduler.
        for name in ("Global.Entry", "Global.AutoCombat.Entry"):
            pipeline[name] = {"next": []}
        for name in ("Activity.Go", "Activity.Select", "Global.Entry",
                     "Global.AutoCombat.Entry"):
            pipeline[name]["action"] = {
                "type": "Custom", "param": {"custom_action": "ReplayAction"}
            }
        pipeline["Activity.Go"]["recognition"] = {
            "type": "Custom", "param": {"custom_recognition": "ReplayScreen"}
        }
        for node in pipeline.values():
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=10, rate_limit=1)
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/activity.json").write_text(
                json.dumps(pipeline), encoding="utf-8"
            )
            resource = Resource()
            resource.register_custom_recognition("ReplayScreen", ActivityScreen(state))
            resource.register_custom_action("ReplayAction", ActivityAction(state))
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
                job = tasker.post_task(entry).wait()
                succeeded = job.status.succeeded
            finally:
                watchdog.cancel()
            self.assertFalse(timed_out.is_set(), state["visited"][:20])
        return state, succeeded

    def test_map_left_after_dungeon_recovers_and_starts_combat(self):
        state, succeeded = self.replay(failed_opens=1)
        self.assertTrue(state["started_combat"], state["visited"])
        self.assertTrue(succeeded)
        self.assertEqual(state["opens"], 2)

    def test_missing_quest_is_not_reported_as_success(self):
        state, succeeded = self.replay(failed_opens=100)
        self.assertFalse(state["started_combat"])
        self.assertFalse(succeeded, state["visited"])
        self.assertLessEqual(state["opens"], 2)

    def test_ready_list_starts_without_recovery(self):
        state, succeeded = self.replay(failed_opens=0)
        self.assertTrue(state["started_combat"], state["visited"])
        self.assertTrue(succeeded)
        self.assertNotIn("Global.Entry", state["visited"])

    def test_starting_on_dungeon_map_returns_home_first(self):
        state, succeeded = self.replay(failed_opens=0, screen="map")
        self.assertTrue(state["started_combat"], state["visited"])
        self.assertTrue(succeeded)
        self.assertEqual(state["visited"][0], "Global.Entry")

    def test_unavailable_activity_entry_does_not_loop(self):
        state, succeeded = self.replay(failed_opens=0, entry_visible=False)
        self.assertFalse(succeeded)
        self.assertFalse(state["started_combat"])
        self.assertLessEqual(state["visited"].count("Global.Entry"), 1)

    def test_first_clear_return_selects_from_current_list_without_reopening(self):
        state, succeeded = self.replay(
            failed_opens=0, screen="quests", first_clear_return=True,
        )
        self.assertTrue(succeeded, state["visited"])
        self.assertTrue(state["started_combat"], state["visited"])
        self.assertEqual(state["wrong_quest_clicks"], 0, state["visited"])
        self.assertEqual(state["opens"], 0, state["visited"])
        self.assertNotIn("Global.Entry", state["visited"])

    def test_home_entry_patterns_reject_quest_card_categories(self):
        for resource, labels, category in (
            ("base", ("活动", "正在举办的活动"), "活动（自由）"),
            ("resource_tw", ("活動", "正在舉辦的活動"), "活動（自由）"),
            ("resource_jp", ("イベント", "開催中のイベント"), "イベント（フリー）"),
            ("resource_en", ("Event", "Current Events"), "Event (Free)"),
        ):
            with self.subTest(resource=resource):
                path = ROOT / "assets/resource" / resource / "pipeline/combat/activity.json"
                node = json.loads(path.read_text(encoding="utf-8"))["Activity.Go"]
                patterns = node["recognition"]["param"]["expected"]
                for label in labels:
                    self.assertTrue(any(re.search(pattern, label) for pattern in patterns), label)
                self.assertFalse(any(re.search(pattern, category) for pattern in patterns))


if __name__ == "__main__":
    unittest.main()
