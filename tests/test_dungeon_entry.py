"""Replay missed dungeon-entry taps through the real MaaFramework scheduler.

The 2026-10-31 trace clicked (1194, 577) in the loose quest-icon match
(1131, 573, 112, 96), then returned home hundreds of times without
clicking the quest button again. Only screen/input boundaries are simulated.

The 2026-11-03 trace dispatched the switch-map tap at (1166, 384),
then ran the configured flower lookup on the unchanged city map.
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
QUEST_BOX = [1131, 573, 112, 96]
MAP_BOX = [1166, 360, 90, 64]
HEADERS = {
    "base": ("切换地图", "返回"),
    "resource_tw": ("切換地圖", "返回"),
    "resource_jp": ("マップ切り替え", "戻る"),
    "resource_en": ("Switch Map", "Back"),
}


class DungeonController(CustomController):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def connect(self):
        return True

    def request_uuid(self):
        return "dungeon-entry-regression"

    def get_features(self):
        return 0

    def screencap(self):
        if self.state["screen"] == "loading":
            self.state["loading_frames"] -= 1
            if self.state["loading_frames"] <= 0:
                self.state["screen"] = "dungeons"
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def click(self, x, y):
        state = self.state
        name = state["matched"]
        state["clicks"].append((name, x, y))
        kind = state["matched_kind"]
        if kind == "quest":
            state["opens"] += 1
            if state["opens"] > state["ignored_opens"]:
                state["screen"] = state["opened_screen"]
            elif state["open_dialog"]:
                state["screen"] = "dialog"
        elif kind == "back":
            state["screen"] = "map"
        elif kind == "map":
            state["map_opens"] += 1
            if state["map_opens"] > state["ignored_map_opens"]:
                state["screen"] = "loading" if state["loading_frames"] else "dungeons"
        elif kind == "stage":
            state["selected"] = True
        # Dispatch can succeed while the game ignores the tap.
        return True


class DungeonScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        screen = self.state["screen"]
        recognition = json.loads(argv.custom_recognition_param)
        kind = recognition["type"]
        params = recognition.get("param", {})
        hit = None
        if kind == "FeatureMatch":
            templates = params["template"]
            if isinstance(templates, str):
                templates = [templates]
            if "map/changemap.png" in templates and screen == "map":
                hit = ("map", MAP_BOX)
            elif ("homepage/quest_off.png" in templates and screen == "home"
                  and self.state["entry_visible"]):
                hit = ("quest", QUEST_BOX)
        elif kind == "TestHome" and screen == "home":
            hit = ("home", [757, 604, 92, 83])
        elif kind == "OCR":
            header, back = HEADERS[self.state["language"]]
            texts = {
                "map": [(header, [1166, 422, 90, 25], "map")],
                "quests": [(back, [32, 20, 65, 40], "back")],
                "dungeons": [(back, [32, 20, 65, 40], "back"),
                             (header, [1028, 10, 200, 45], "selector"),
                             ("異境花园", [274, 308, 150, 42], "stage")],
            }.get(screen, [])
            patterns = params["expected"]
            if isinstance(patterns, str):
                patterns = [patterns]
            rx, ry, rw, rh = params.get("roi", [0, 0, 1280, 720])
            for text, box, matched_kind in texts:
                x, y, w, h = box
                if (rx <= x and ry <= y and x + w <= rx + rw and y + h <= ry + rh
                        and any(re.search(pattern, text) for pattern in patterns)):
                    hit = (matched_kind, box)
                    break
        if hit:
            self.state["matched"] = argv.node_name
            self.state["matched_kind"] = hit[0]
            return hit[1]
        return None


class DungeonAction(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        if argv.node_name == "Global.Entry":
            self.state["recoveries"] += 1
            self.state["screen"] = "home"
        elif argv.node_name == "Dungeon.Activity.Entry":
            self.state["consumer_screens"].append(self.state["screen"])
        return True


class DungeonEntryTests(unittest.TestCase):
    def replay(self, screen="home", ignored_opens=0, opened_screen="map",
               entry_visible=True, open_dialog=False, ignored_map_opens=0,
               loading_frames=0, language="base"):
        state = dict(screen=screen, ignored_opens=ignored_opens,
                     opened_screen=opened_screen, entry_visible=entry_visible,
                     open_dialog=open_dialog, matched=None, clicks=[],
                     opens=0, recoveries=0, matched_kind=None,
                     ignored_map_opens=ignored_map_opens, map_opens=0,
                     loading_frames=loading_frames, language=language,
                     selected=False, consumer_screens=[])
        source = json.loads((ROOT / "assets/resource/base/pipeline/combat/dungeon.json")
                            .read_text(encoding="utf-8"))
        names = {"Dungeon.Entry", "Dungeon.Change1", "Dungeon.Change1.1",
                 "Dungeon.Change2", "Dungeon.OpenMap", "Dungeon.Activity.Entry",
                 "Dungeon.Activity.Choice"}
        pipeline = {name: node for name, node in source.items()
                    if name in names or name.startswith("Dungeon.Recover")}
        if language != "base":
            overlay = json.loads((ROOT / "assets/resource" / language
                                  / "pipeline/combat/dungeon.json").read_text(encoding="utf-8"))
            for name, node in overlay.items():
                if name in pipeline and "recognition" in node:
                    pipeline[name]["recognition"]["param"].update(node["recognition"]["param"])
        # Retain the interface producer's actual continuation. A successful
        # input dispatch must not advance it while the city map is still open.
        interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))
        overrides = interface["option"]["custom_stage_dungeon"]["pipeline_override"]
        pipeline["Dungeon.Change2"].update(overrides["Dungeon.Change2"])
        pattern = overrides["Dungeon.Activity.Choice"]["recognition"]["param"]["expected"]
        pipeline["Dungeon.Activity.Choice"]["recognition"]["param"]["expected"] = (
            pattern.format(**{"自定义关卡": "花园"}))
        # End at the stage-selection boundary, before any quest can launch.
        pipeline["Dungeon.Activity.Choice"]["next"] = []
        pipeline["Dungeon.Activity.Choice"]["on_error"] = []
        pipeline["Global.Entry"] = {
            "action": {"type": "Custom", "param": {"custom_action": "ReplayAction"}},
        }
        pipeline["Global.HomePage"] = {"recognition": {"type": "TestHome"}}
        for name in ("Dungeon.Entry", "Dungeon.Activity.Entry"):
            pipeline[name]["action"] = {
                "type": "Custom", "param": {"custom_action": "ReplayAction"},
            }
        for node in pipeline.values():
            if "recognition" in node:
                node["recognition"] = {
                    "type": "Custom", "param": {
                        "custom_recognition": "ReplayScreen",
                        "custom_recognition_param": node["recognition"],
                    },
                }
        # Keep production Click targets and next/on_error/JumpBack/max_hit.
        for node in pipeline.values():
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=20, rate_limit=1)
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/dungeon.json").write_text(
                json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("ReplayScreen", DungeonScreen(state))
            resource.register_custom_action("ReplayAction", DungeonAction(state))
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = DungeonController(state)
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
                succeeded = tasker.post_task("Dungeon.Entry").wait().status.succeeded
            finally:
                watchdog.cancel()
            self.assertFalse(timed_out.is_set(), state)
        return state, succeeded

    def test_ignored_first_quest_tap_is_retried(self):
        state, succeeded = self.replay(ignored_opens=1)
        self.assertTrue(succeeded, state)
        self.assertEqual(state["screen"], "dungeons")
        self.assertEqual(state["opens"], 2)

    def test_dialog_after_first_tap_recovers_then_retries(self):
        state, succeeded = self.replay(ignored_opens=1, open_dialog=True)
        self.assertTrue(succeeded, state)
        self.assertEqual(state["screen"], "dungeons")
        self.assertEqual(state["opens"], 2)
        self.assertEqual(state["recoveries"], 1)

    def test_home_entry_reaches_dungeons_without_recovery(self):
        state, succeeded = self.replay()
        self.assertTrue(succeeded, state)
        self.assertEqual(state["screen"], "dungeons")
        self.assertEqual(state["opens"], 1)
        self.assertEqual(state["recoveries"], 0)

    def test_quest_tap_stays_inside_button_despite_loose_match(self):
        state, succeeded = self.replay()
        self.assertTrue(succeeded, state)
        for name, x, y in state["clicks"]:
            if name == "Dungeon.Change1":
                self.assertTrue(1180 <= x <= 1230 and 625 <= y <= 670, (x, y))

    def test_opened_quest_list_returns_to_map(self):
        state, succeeded = self.replay(opened_screen="quests")
        self.assertTrue(succeeded, state)
        self.assertEqual(state["screen"], "dungeons")
        self.assertEqual([name for name, _, _ in state["clicks"]],
                         ["Dungeon.Change1", "Dungeon.Change1.1", "Dungeon.OpenMap",
                          "Dungeon.Activity.Choice"])

    def test_starting_on_map_skips_home_entry(self):
        state, succeeded = self.replay(screen="map")
        self.assertTrue(succeeded, state)
        self.assertEqual(state["screen"], "dungeons")
        self.assertEqual(state["opens"], 0)
        self.assertEqual(state["recoveries"], 0)

    def test_unknown_starting_screen_recovers_home(self):
        state, succeeded = self.replay(screen="dialog")
        self.assertTrue(succeeded, state)
        self.assertEqual(state["screen"], "dungeons")
        self.assertEqual(state["recoveries"], 1)

    def test_unresponsive_quest_button_stops_as_failure(self):
        state, succeeded = self.replay(ignored_opens=100)
        self.assertFalse(succeeded, state)
        self.assertNotEqual(state["screen"], "dungeons")
        self.assertGreaterEqual(state["opens"], 2)
        self.assertLessEqual(state["opens"], 3)

    def test_missing_quest_button_stops_as_failure(self):
        state, succeeded = self.replay(entry_visible=False)
        self.assertFalse(succeeded, state)
        self.assertNotEqual(state["screen"], "dungeons")
        self.assertLessEqual(state["recoveries"], 2)

    def test_ignored_switch_tap_retries_before_entering_configured_stage(self):
        state, succeeded = self.replay(screen="map", ignored_map_opens=1)
        self.assertTrue(succeeded, state)
        self.assertTrue(state["selected"], state)
        self.assertEqual(state["map_opens"], 2)
        self.assertEqual(state["consumer_screens"], ["dungeons"])

    def test_unresponsive_switch_does_not_search_for_stage_on_city_map(self):
        state, succeeded = self.replay(screen="map", ignored_map_opens=100)
        self.assertFalse(succeeded, state)
        self.assertFalse(state["selected"], state)
        self.assertEqual(state["consumer_screens"], [])
        self.assertEqual(state["map_opens"], 3)

    def test_switch_click_uses_inner_button_area(self):
        state, succeeded = self.replay(screen="map")
        self.assertTrue(succeeded, state)
        for name, x, y in state["clicks"]:
            if name == "Dungeon.OpenMap":
                self.assertTrue(1200 <= x <= 1220 and 390 <= y <= 410, (x, y))

    def test_already_open_selector_does_not_click_back_or_reopen(self):
        state, succeeded = self.replay(screen="dungeons")
        self.assertTrue(succeeded, state)
        self.assertTrue(state["selected"], state)
        self.assertEqual(state["map_opens"], 0)
        self.assertEqual(state["recoveries"], 0)
        self.assertEqual(state["opens"], 0)

    def test_loading_between_switch_and_selector_waits_for_header(self):
        state, succeeded = self.replay(screen="map", loading_frames=3)
        self.assertTrue(succeeded, state)
        self.assertTrue(state["selected"], state)
        self.assertEqual(state["map_opens"], 1)
        self.assertEqual(state["consumer_screens"], ["dungeons"])

    def test_localized_selector_headers_preserve_the_same_route(self):
        for language in HEADERS:
            with self.subTest(language=language):
                state, succeeded = self.replay(screen="map", language=language)
                self.assertTrue(succeeded, state)
                self.assertTrue(state["selected"], state)
                self.assertEqual(state["consumer_screens"], ["dungeons"])


if __name__ == "__main__":
    unittest.main()
