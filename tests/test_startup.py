"""Replay startup exits through the native MaaFramework scheduler.

Only device state and visual recognition are simulated. Production next,
on_error and JumpBack edges decide whether login and announcements finish.
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


class StartupController(CustomController):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def connect(self):
        return True

    def request_uuid(self):
        return "startup-routing-regression"

    def get_features(self):
        return 0

    def start_app(self, intent):
        self.state["starts"] += 1
        if self.state["screen"] == "launcher":
            self.state["screen"] = self.state["launch_screen"]
        return True

    def screencap(self):
        if self.state["screen"] == "loading":
            self.state["loading_frames"] -= 1
            if self.state["loading_frames"] <= 0:
                self.state["screen"] = "title"
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def click(self, x, y):
        state = self.state
        name = state["matched"]
        state["clicks"].append(name)
        if name == "Startup.OpenGame.Title":
            if state["network_failures"]:
                state["network_failures"] -= 1
                state["screen"] = "network-error"
            else:
                state["screen"] = state["after_title"]
        elif name == "Startup.Update_1":
            state["screen"] = "loading"
        elif name == "Global.GetRidOfNetworkError":
            state["screen"] = "title"
        elif name == "Global.LoginReward":
            state["screen"] = "announcement"
        elif name == "Global.AnnouncementShutdown":
            state["announcements"] -= 1
            if state["announcements"] <= 0:
                state["screen"] = "home"
        elif name == "Global.GoHomePage":
            state["screen"] = "home"
        return True


class StartupScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        screen = self.state["screen"]
        recognition = json.loads(argv.custom_recognition_param)
        kind = recognition["type"]
        params = recognition.get("param", {})
        hit = False
        if kind in ("FeatureMatch", "TemplateMatch"):
            templates = params["template"]
            if isinstance(templates, str):
                templates = [templates]
            hit = (("titlelogo.png" in templates and screen == "title")
                   or ("login.png" in templates and screen == "loading"))
        elif kind == "ColorMatch":
            hit = (screen == "home" and params["lower"] == [[244, 237, 0]])
        elif kind == "OCR":
            texts = {
                "update": ["OK"],
                "reward": ["GET!"],
                "announcement": ["关闭"],
                "network-error": ["Unable to complete SSL connection", "CLOSE"],
                "back": ["返回"],
            }.get(screen, [])
            patterns = params["expected"]
            if isinstance(patterns, str):
                patterns = [patterns]
            hit = any(re.search(pattern, text) for pattern in patterns for text in texts)
        if hit:
            self.state["matched"] = argv.node_name
            return [600, 570, 80, 48]
        return None


class GoBackAction(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        self.state["backs"] += 1
        if self.state["screen"] != "back":
            return False
        self.state["screen"] = "home"
        return True


class StartupTests(unittest.TestCase):
    def replay(self, screen="title", entry="Startup.Entry", after_title="announcement",
               launch_screen="loading", network_failures=0, announcements=1):
        state = dict(screen=screen, after_title=after_title, launch_screen=launch_screen,
                     starts=0, clicks=[], matched=None, loading_frames=4, backs=0,
                     network_failures=network_failures, announcements=announcements)
        pipeline = {}
        for filename in ("startup.json", "global.json"):
            pipeline.update(json.loads((ROOT / "assets/resource/base/pipeline" / filename)
                                       .read_text(encoding="utf-8")))
        for node in pipeline.values():
            if "recognition" in node:
                node["recognition"] = {"type": "Custom", "param": {
                    "custom_recognition": "StartupScreen",
                    "custom_recognition_param": node["recognition"],
                }}
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=30, rate_limit=1)
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/startup.json").write_text(json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("StartupScreen", StartupScreen(state))
            resource.register_custom_action("GoBack", GoBackAction(state))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = StartupController(state)
            self.assertTrue(controller.post_connection().wait().status.succeeded)
            tasker = Tasker()
            self.assertTrue(tasker.bind(resource, controller))
            timed_out = threading.Event()

            def stop_loop():
                timed_out.set()
                tasker.post_stop()

            watchdog = threading.Timer(3, stop_loop)
            watchdog.start()
            try:
                succeeded = tasker.post_task(entry).wait().status.succeeded
            finally:
                watchdog.cancel()
            self.assertFalse(timed_out.is_set(), state)
        self.assertTrue(succeeded, state)
        self.assertEqual(state["screen"], "home", state)
        return state

    def test_global_recovery_on_title_finishes_login_and_announcement(self):
        state = self.replay(entry="Global.Entry")
        self.assertEqual(state["clicks"], ["Startup.OpenGame.Title", "Global.AnnouncementShutdown"])
        self.assertEqual(state["starts"], 0)

    def test_title_can_go_directly_to_announcement(self):
        state = self.replay(entry="Startup.OpenGame.Title")
        self.assertEqual(state["clicks"], ["Startup.OpenGame.Title", "Global.AnnouncementShutdown"])

    def test_cold_launch_retains_loading_and_title_sequence(self):
        state = self.replay(screen="launcher")
        self.assertEqual(state["starts"], 1)
        self.assertEqual(state["clicks"], ["Startup.OpenGame.Title", "Global.AnnouncementShutdown"])

    def test_update_confirmation_returns_to_loading_and_title(self):
        state = self.replay(screen="launcher", launch_screen="update")
        self.assertEqual(state["starts"], 1)
        self.assertEqual(state["clicks"], ["Startup.Update_1", "Startup.OpenGame.Title",
                                           "Global.AnnouncementShutdown"])

    def test_startup_on_home_does_not_launch_app(self):
        state = self.replay(screen="home")
        self.assertEqual(state["starts"], 0)
        self.assertEqual(state["clicks"], [])

    def test_startup_on_announcement_does_not_launch_app(self):
        state = self.replay(screen="announcement")
        self.assertEqual(state["starts"], 0)
        self.assertEqual(state["clicks"], ["Global.AnnouncementShutdown"])

    def test_reward_still_closes_following_announcement(self):
        state = self.replay(after_title="reward")
        self.assertEqual(state["clicks"], ["Startup.OpenGame.Title", "Global.LoginReward",
                                           "Global.AnnouncementShutdown"])

    def test_title_can_go_directly_to_home(self):
        state = self.replay(after_title="home")
        self.assertEqual(state["clicks"], ["Startup.OpenGame.Title"])

    def test_multiple_announcements_keep_existing_close_loop(self):
        state = self.replay(announcements=2)
        self.assertEqual(state["clicks"].count("Global.AnnouncementShutdown"), 2)

    def test_network_error_after_title_closes_and_retries_login(self):
        state = self.replay(network_failures=1)
        self.assertEqual(state["clicks"], ["Startup.OpenGame.Title", "Global.GetRidOfNetworkError",
                                           "Startup.OpenGame.Title", "Global.AnnouncementShutdown"])
        self.assertEqual(state["starts"], 0)

    def test_loading_error_exit_recovers_through_global(self):
        state = self.replay(screen="launcher", launch_screen="network-error")
        self.assertEqual(state["starts"], 1)
        self.assertEqual(state["clicks"], ["Global.GetRidOfNetworkError", "Startup.OpenGame.Title",
                                           "Global.AnnouncementShutdown"])

    def test_startup_external_edges_share_global_exit(self):
        startup = json.loads((ROOT / "assets/resource/base/pipeline/startup.json").read_text(encoding="utf-8"))
        for name, node in startup.items():
            for field in ("next", "on_error"):
                for target in node.get(field, []):
                    target = re.sub(r"^\[[^]]+\]", "", target)
                    if target not in startup:
                        self.assertEqual(target, "Global.Entry", (name, field, target))


if __name__ == "__main__":
    unittest.main()
