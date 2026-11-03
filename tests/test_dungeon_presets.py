"""Exercise the four built-in dungeon routes with the real Maa scheduler.

Localized strings are fixtures from the game's word table. OCR/device input
is simulated here; native OCR against captured game frames is verified separately.
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
CASES = {
    "生命树海": ("woods", "life"), "强力树海": ("woods", "power"),
    "生命花园": ("garden", "life"), "强力花园": ("garden", "power"),
}
TEXT = {
    "base": {
        "header": "切换地图", "explore": "探索", "interface": "interface_zh.json",
        "woods": "秘岛森林", "garden": "异境花园",
        "episodes": ["探索/生命树海", "探索/强力树海", "探索/生命花园", "探索/强力花园"],
        "labels": ["生命树海", "强力树海", "生命花园", "强力花园"],
    },
    "resource_tw": {
        "header": "切換地圖", "explore": "探索", "interface": "interface_tw.json",
        "woods": "神秘島密林", "garden": "異境花園",
        "episodes": ["探索/生命的樹海", "探索/強力的樹海", "探索/生命的花園", "探索/強力的花園"],
        "labels": ["生命的樹海", "強力的樹海", "生命的花園", "強力的花園"],
    },
    "resource_jp": {
        "header": "マップ切り替え", "explore": "探索", "interface": "interface_jp.json",
        "woods": "秘島の密林", "garden": "異境の花園",
        "episodes": ["探索/生命の樹海", "探索/強力の樹海", "探索/生命の花園", "探索/強力の花園"],
        "labels": ["生命の樹海", "強力の樹海", "生命の花園", "強力の花園"],
    },
    "resource_en": {
        "header": "Switch Map", "explore": "Exploration", "interface": "interface_en.json",
        "woods": "Hidden Island Thicket", "garden": "Exotic Garden",
        "episodes": ["Exploring the Woods of Life", "Exploring the Woods of Power",
                     "Exploring the Garden of Life", "Exploring the Garden of Power"],
        "labels": ["Woods of Life", "Woods of Power", "Garden of Life", "Garden of Power"],
    },
}


def merge(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = value


class PresetController(CustomController):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def connect(self):
        return True

    def request_uuid(self):
        return "dungeon-preset-regression"

    def get_features(self):
        return 0

    def screencap(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def click(self, x, y):
        kind, value = self.state["matched"]
        self.state["clicks"].append((kind, value))
        if kind == "map":
            self.state.update(area=value, screen="map")
        elif kind == "explore":
            self.state["screen"] = "quests"
        elif kind == "episode":
            self.state.update(selected=value, screen="prebattle")
        return True


class PresetScreen(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        s = self.state
        text = TEXT[s["language"]]
        candidates = []
        if s["screen"] == "selector":
            candidates = [(text["header"], [1020, 5, 200, 50], "header", None),
                          (text["woods"], [100, 160, 420, 60], "map", "woods"),
                          (text["garden"], [100, 300, 420, 60], "map", "garden")]
        elif s["screen"] in ("map", "quests"):
            candidates = [(text["explore"], [593, 315, 93, 51], "explore", None)]
            if s["screen"] == "quests":
                for i, (area, kind) in enumerate(CASES.values()):
                    if area == s["area"] and kind != s["missing"]:
                        title = text["episodes"][i]
                        if s["ocr_variant"]:
                            title = title.replace("强", "強").replace("园", "園").replace("树", "樹")
                        candidates.append((title, [662, 99 if kind == "life" else 227, 340, 41],
                                           "episode", (area, kind)))
                # This same map name on quest badges must not act as the selector.
                candidates.append((text[s["area"]], [554, 112, 86, 28], "map", s["area"]))
        params = json.loads(argv.custom_recognition_param)
        patterns = params["expected"]
        if isinstance(patterns, str):
            patterns = [patterns]
        rx, ry, rw, rh = params.get("roi", [0, 0, 1280, 720])
        for title, box, kind, value in candidates:
            x, y, w, h = box
            if (rx <= x and ry <= y and x + w <= rx + rw and y + h <= ry + rh
                    and any(re.search(p, title) for p in patterns)):
                s["matched"] = (kind, value)
                return box
        return None


class CombatBoundary(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        self.state["reached_combat"] = True
        return True


class DungeonPresetTests(unittest.TestCase):
    def replay(self, case_name, language="base", returning=False, ocr_variant=False, missing=None):
        interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))
        case = next((c for c in interface["option"]["choose_stage_dungeon"]["cases"]
                     if c["name"] == case_name), None)
        self.assertIsNotNone(case, f"Missing built-in dungeon option: {case_name}")
        source = json.loads((ROOT / "assets/resource/base/pipeline/combat/dungeon.json")
                            .read_text(encoding="utf-8"))
        pipeline = {"Dungeon.Change2": source["Dungeon.Change2"]}
        for bundle in (["base"] if language == "base" else ["base", language]):
            folder = ROOT / "assets/resource" / bundle / "pipeline/combat"
            merge(pipeline, json.loads((folder / "dungeon_presets.json").read_text(encoding="utf-8")))
            if bundle != "base":
                old = json.loads((folder / "dungeon.json").read_text(encoding="utf-8"))
                merge(pipeline["Dungeon.Change2"], old["Dungeon.Change2"])
        merge(pipeline, case["pipeline_override"])
        area, _ = CASES[case_name]
        state = dict(language=language, area=area, screen="quests" if returning else "selector",
                     matched=None, selected=None, clicks=[], reached_combat=False,
                     ocr_variant=ocr_variant, missing=missing)
        pipeline["Global.AutoCombat.Entry"] = {"action": {
            "type": "Custom", "param": {"custom_action": "CombatBoundary"}}}
        for node in pipeline.values():
            if "recognition" in node:
                params = node["recognition"]["param"]
                node["recognition"] = {"type": "Custom", "param": {
                    "custom_recognition": "PresetScreen", "custom_recognition_param": params}}
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0, post_wait_freezes=0,
                        timeout=25, rate_limit=1)
        start = "Global.AutoCombat.BacktoEntry" if returning else "Dungeon.Change2"
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "pipeline").mkdir()
            (folder / "pipeline/presets.json").write_text(json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("PresetScreen", PresetScreen(state))
            resource.register_custom_action("CombatBoundary", CombatBoundary(state))
            self.assertTrue(resource.post_bundle(folder).wait().status.succeeded)
            controller = PresetController(state)
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
                succeeded = tasker.post_task(start).wait().status.succeeded
            finally:
                watchdog.cancel()
            self.assertFalse(timed_out.is_set(), state)
        return succeeded, state

    def test_each_localized_option_selects_its_own_map_and_episode(self):
        for language in TEXT:
            for case_name, target in CASES.items():
                with self.subTest(language=language, case=case_name):
                    succeeded, state = self.replay(case_name, language)
                    self.assertTrue(succeeded, state)
                    self.assertTrue(state["reached_combat"], state)
                    self.assertEqual(state["selected"], target)
                    self.assertEqual(state["clicks"], [("map", target[0]), ("explore", None),
                                                      ("episode", target)])

    def test_first_clear_return_reselects_same_episode_without_reopening_map(self):
        for case_name, target in CASES.items():
            with self.subTest(case=case_name):
                succeeded, state = self.replay(case_name, returning=True)
                self.assertTrue(succeeded, state)
                self.assertEqual(state["clicks"], [("episode", target)])

    def test_simplified_chinese_accepts_observed_traditional_ocr_variants(self):
        for case_name, target in CASES.items():
            with self.subTest(case=case_name):
                succeeded, state = self.replay(case_name, ocr_variant=True)
                self.assertTrue(succeeded, state)
                self.assertEqual(state["selected"], target)

    def test_missing_episode_does_not_select_the_other_difficulty(self):
        for case_name, target in CASES.items():
            with self.subTest(case=case_name):
                succeeded, state = self.replay(case_name, missing=target[1])
                self.assertFalse(succeeded, state)
                self.assertFalse(state["reached_combat"], state)
                self.assertIsNone(state["selected"], state)

    def test_interface_labels_use_game_names_without_exploration_prefix(self):
        interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))
        cases = {c["name"]: c for c in interface["option"]["choose_stage_dungeon"]["cases"]}
        for language, fixture in TEXT.items():
            labels = json.loads((ROOT / "assets/resource" / language / fixture["interface"])
                                .read_text(encoding="utf-8"))
            for name, expected in zip(CASES, fixture["labels"]):
                with self.subTest(language=language, case=name):
                    self.assertIn(name, cases)
                    self.assertEqual(labels[cases[name]["label"].removeprefix("$")], expected)


if __name__ == "__main__":
    unittest.main()
