"""Reward recovery through announcements and home navigation."""
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


class FrameController(CustomController):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame

    def connect(self):
        return True

    def request_uuid(self):
        return "reward-recovery-regression"

    def screencap(self):
        return self.frame


class RouteScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        screen = self.state["screen"]
        if ((screen == "web" and argv.node_name == "Global.AnnouncementWebClose")
                or (screen == "menu" and argv.node_name in (
                    "Global.AnnouncementListCollapse", "Global.HomePage"))
                or (screen == "back" and argv.node_name == "Global.GoBackToHomePage")
                or (screen == "home" and argv.node_name in (
                    "Global.HomePage", "Reward.Click", "Reward.Gift"))):
            return [40, 540, 60, 30]
        return None


class RouteAction(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        self.state["actions"].append(argv.node_name)
        if argv.node_name == "Global.AnnouncementWebClose":
            self.state["screen"] = self.state.get("after_web", "home")
        elif argv.node_name in ("Global.GoBackToHomePage", "Global.AnnouncementListCollapse"):
            self.state["screen"] = "home"
        return True


class RewardRecoveryTests(unittest.TestCase):
    def run_task(self, resource, controller, entry, overrides=None):
        self.assertTrue(controller.post_connection().wait().status.succeeded)
        tasker = Tasker()
        self.assertTrue(tasker.bind(resource, controller))
        timed_out = threading.Event()

        def stop():
            timed_out.set()
            tasker.post_stop()

        watchdog = threading.Timer(5, stop)
        watchdog.start()
        try:
            job = tasker.post_task(entry, overrides or {}).wait()
            succeeded = job.status.succeeded
        finally:
            watchdog.cancel()
        self.assertFalse(timed_out.is_set())
        return succeeded

    def replay_entry(self, screen, after_back=False, expanded=False):
        state = {"screen": screen, "actions": [], "after_web": "menu" if expanded else "home"}
        pipeline = {}
        for filename in ("reward.json", "global.json", "startup.json"):
            pipeline.update(json.loads((ROOT / "assets/resource/base/pipeline" / filename)
                                       .read_text(encoding="utf-8")))
        for node in pipeline.values():
            if "recognition" in node:
                node["recognition"] = {"type": "Custom", "param": {
                    "custom_recognition": "RouteScreen"}}
            if node.get("action", {}).get("type") in ("Click", "Custom", "StartApp"):
                node["action"] = {"type": "Custom", "param": {"custom_action": "RouteAction"}}
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=20, rate_limit=1)
        pipeline["Reward.Click"]["next"] = []
        pipeline["Reward.Gift"]["next"] = []
        # The anniversary check has its own end-to-end replay; exercise the
        # ordinary claiming route here, including its announcement recovery.
        pipeline["Reward.Entry"]["next"] = ["Reward.Claim.Entry"]
        entry = "Reward.Entry"
        if after_back:
            entry = "Replay.AfterBack"
            pipeline[entry] = {"next": pipeline["Reward.Back"]["next"],
                               "timeout": 20, "rate_limit": 1,
                               "pre_delay": 0, "post_delay": 0}
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/recovery.json").write_text(json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("RouteScreen", RouteScreen(state))
            resource.register_custom_action("RouteAction", RouteAction(state))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = FrameController(np.zeros((720, 1280, 3), dtype=np.uint8))
            self.assertTrue(self.run_task(resource, controller, entry))
        return state["actions"]

    def test_web_announcement_closes_and_resumes_reward_entry(self):
        self.assertEqual(self.replay_entry("web"), ["Global.AnnouncementWebClose", "Reward.Click"])

    def test_entry_recovers_before_the_missions_button_is_visible(self):
        self.assertEqual(self.replay_entry("back"), ["Global.GoBackToHomePage", "Reward.Click"])

    def test_web_announcement_after_back_resumes_at_gift(self):
        self.assertEqual(self.replay_entry("web", after_back=True),
                         ["Global.AnnouncementWebClose", "Reward.Gift"])

    def test_web_close_also_collapses_the_list_covering_missions(self):
        self.assertEqual(self.replay_entry("web", expanded=True),
                         ["Global.AnnouncementWebClose", "Global.AnnouncementListCollapse",
                          "Reward.Click"])


if __name__ == "__main__":
    unittest.main()
