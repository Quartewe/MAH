"""Replay the force-support option from the weekly task entry."""

import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest

import numpy as np
from maa.controller import CustomController
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.resource import Resource
from maa.tasker import Tasker

from agent_modules import load_agent_module


ROOT = Path(__file__).resolve().parents[1]


class Controller(CustomController):
    def connect(self):
        return True

    def request_uuid(self):
        return "weekly-support-option"

    def screencap(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class Screen(CustomRecognition):
    def __init__(self, completed):
        super().__init__()
        self.completed = completed

    def analyze(self, context, argv):
        if argv.node_name == "CheckWeeklyMissions.Search" and not self.completed:
            return None
        return [40, 540, 60, 30]


class Action(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        self.state["actions"].append(argv.node_name)
        return True


class Logic(CustomAction):
    def __init__(self, state, action):
        super().__init__()
        self.state, self.action = state, action

    def run(self, context, argv):
        self.state["decisions"].append(argv.node_name)
        return self.action.run(context, argv)


class WeeklySupportOptionTests(unittest.TestCase):
    def replay(self, force, completed):
        state = {"actions": [], "decisions": []}
        shared = NS(is_first_run=False, show_support=completed)
        module = load_agent_module("agent/custom/action/missions_logic.py", info_share=shared)
        pipeline = {}
        for name in ("check_weekly_missions", "show_supporter_screen"):
            path = ROOT / "assets/resource/base/pipeline/weekly" / (name + ".json")
            pipeline.update(json.loads(path.read_text(encoding="utf-8")))
        for node in pipeline.values():
            if "recognition" in node:
                node["recognition"] = {"type": "Custom", "param": {"custom_recognition": "Screen"}}
            if ("action" in node
                    and node["action"].get("param", {}).get("custom_action") != "MissionLogic"):
                node["action"] = {"type": "Custom", "param": {"custom_action": "Action"}}
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=30, rate_limit=1)
        pipeline["Global.Entry"] = {}
        pipeline["Global.HomePage"] = {}
        interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))
        task = next(task for task in interface["task"] if task["entry"] == "CheckWeeklyMissions.Entry")
        self.assertIn("force_open_support", task["option"])
        choice = next(case for case in interface["option"]["force_open_support"]["cases"]
                      if case["name"] == ("Yes" if force else "No"))
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/replay.json").write_text(json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("Screen", Screen(completed))
            resource.register_custom_action("Action", Action(state))
            resource.register_custom_action("MissionLogic", Logic(state, module.MissionLogic()))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = Controller()
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
                result = tasker.post_task("CheckWeeklyMissions.Entry",
                                          choice.get("pipeline_override", {})).wait()
                self.assertTrue(result.status.succeeded, state)
            finally:
                watchdog.cancel()
            self.assertFalse(timed_out.is_set(), state)
        return state

    def test_force_opens_support_without_running_the_status_decision(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                state = self.replay(force=True, completed=completed)
                self.assertNotIn("CheckWeeklyMissions.Stop", state["decisions"])
                self.assertIn("ShowSupporterScreen.Completed", state["actions"])
                self.assertFalse(any(name.startswith("CheckWeeklyMissions.") for name in state["actions"]), state)

    def test_disabled_force_keeps_completed_support_mission_skipped(self):
        state = self.replay(force=False, completed=True)
        self.assertIn("CheckWeeklyMissions.Stop", state["decisions"])
        self.assertNotIn("ShowSupporterScreen.Open", state["actions"])

    def test_disabled_force_still_opens_for_an_unfinished_support_mission(self):
        state = self.replay(force=False, completed=False)
        self.assertIn("CheckWeeklyMissions.Stop", state["decisions"])
        self.assertIn("ShowSupporterScreen.Completed", state["actions"])


if __name__ == "__main__":
    unittest.main()
