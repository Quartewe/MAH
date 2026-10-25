"""Replay reward-dialog transitions through the real MaaFramework scheduler.

The installed 2026-10-25 15:39:53 trace recognized CLOSE together with
Loading on the rainbow-shard dialog, dispatched CLOSE and Back once each,
then timed out looking for the home-screen gift entry.
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


class RewardController(CustomController):
    def connect(self):
        return True

    def request_uuid(self):
        return "reward-dialog-regression"

    def screencap(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class RewardScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        screen = self.state["screen"]
        # Back remains visible behind the reward dialog, as in the real OCR.
        texts = []
        if screen in ("missions", "dialog"):
            texts.append(("返回", [32, 46, 65, 34]))
        if screen == "dialog":
            texts.append(("CLOSE", [610, 460, 59, 20]))
        if screen == "missions":
            texts.append(("全部领取", [1115, 117, 97, 34]))
        if screen == "home":
            texts.append(("礼物", [47, 541, 41, 25]))
        patterns = json.loads(argv.custom_recognition_param)["expected"]
        for text, box in texts:
            if any(re.search(pattern, text) for pattern in patterns):
                return box
        return None


class RewardAction(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        state = self.state
        state["visited"].append(argv.node_name)
        if argv.node_name == "Reward.Get":
            state["screen"] = "dialog" if state["dialogs"] else "missions"
        elif argv.node_name == "Reward.Get1":
            state["close_clicks"] += 1
            if state["close_clicks"] > state["ignored_close_clicks"]:
                state["dialogs"] -= 1
                state["screen"] = "dialog" if state["dialogs"] else "missions"
        elif argv.node_name == "Reward.Back":
            state["back_clicks"] += 1
            if (state["screen"] == "missions"
                    and state["back_clicks"] > state["ignored_back_clicks"]):
                state["screen"] = "home"
        elif argv.node_name == "Reward.Gift":
            state["gift_opened"] = True
        # Input dispatch succeeds even when loading/modal state eats the tap.
        return True


class RewardTests(unittest.TestCase):
    def replay(self, dialogs=1, ignored_close_clicks=0, ignored_back_clicks=0):
        state = dict(screen="missions", dialogs=dialogs,
                     ignored_close_clicks=ignored_close_clicks,
                     ignored_back_clicks=ignored_back_clicks,
                     close_clicks=0, back_clicks=0, gift_opened=False, visited=[])
        pipeline = json.loads((ROOT / "assets/resource/base/pipeline/reward.json")
                              .read_text(encoding="utf-8"))
        pipeline = {name: pipeline[name] for name in (
            "Reward.Get", "Reward.Get1", "Reward.Back", "Reward.Gift")}
        # Replace OCR/input boundaries only; retain production next/max_hit.
        for name in ("Reward.Get", "Reward.Get1", "Reward.Back", "Reward.Gift"):
            node = pipeline[name]
            params = node["recognition"]["param"]
            node["recognition"] = {
                "type": "Custom", "param": {
                    "custom_recognition": "RewardScreen",
                    "custom_recognition_param": params,
                },
            }
            node["action"] = {
                "type": "Custom", "param": {"custom_action": "RewardAction"},
            }
        # Stop at the first gift-entry action: the failing transition's consumer.
        pipeline["Reward.Gift"]["next"] = []
        for node in pipeline.values():
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=20, rate_limit=1)
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/reward.json").write_text(
                json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("RewardScreen", RewardScreen(state))
            resource.register_custom_action("RewardAction", RewardAction(state))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = RewardController()
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
                succeeded = tasker.post_task("Reward.Get").wait().status.succeeded
            finally:
                watchdog.cancel()
            self.assertFalse(timed_out.is_set(), state["visited"][:20])
        return state, succeeded

    def test_normal_and_empty_rewards_reach_gift(self):
        for dialogs in (0, 1):
            with self.subTest(dialogs=dialogs):
                state, succeeded = self.replay(dialogs=dialogs)
                self.assertTrue(succeeded, state["visited"])
                self.assertTrue(state["gift_opened"], state["visited"])
                self.assertEqual(state["close_clicks"], dialogs)
                self.assertEqual(state["back_clicks"], 1)

    def test_close_ignored_while_loading_is_retried(self):
        state, succeeded = self.replay(ignored_close_clicks=1)
        self.assertTrue(succeeded, state["visited"])
        self.assertTrue(state["gift_opened"])
        self.assertEqual(state["close_clicks"], 2)
        self.assertEqual(state["back_clicks"], 1)

    def test_consecutive_reward_dialogs_close_before_back(self):
        state, succeeded = self.replay(dialogs=2)
        self.assertTrue(succeeded, state["visited"])
        self.assertTrue(state["gift_opened"])
        self.assertEqual(state["close_clicks"], 2)
        self.assertEqual(state["back_clicks"], 1)

    def test_back_ignored_during_transition_is_retried(self):
        state, succeeded = self.replay(ignored_back_clicks=1)
        self.assertTrue(succeeded, state["visited"])
        self.assertTrue(state["gift_opened"])
        self.assertEqual(state["back_clicks"], 2)

    def test_unresponsive_close_or_back_finishes_as_failure(self):
        for ignored in ("ignored_close_clicks", "ignored_back_clicks"):
            with self.subTest(ignored=ignored):
                state, succeeded = self.replay(**{ignored: 100})
                self.assertFalse(succeeded, state["visited"])
                self.assertFalse(state["gift_opened"])
                self.assertLessEqual(state["close_clicks"], 10)
                self.assertLessEqual(state["back_clicks"], 10)


if __name__ == "__main__":
    unittest.main()
