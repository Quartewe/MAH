"""Replay daily-event discovery, one battle and ordinary claiming in Maa."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
import threading
import traceback
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import numpy as np
from maa.controller import CustomController
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.resource import Resource
from maa.tasker import Tasker

from agent_modules import load_agent_module


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "Reward.SpecialDaily"
ACTIVE_DAY = datetime(2026, 11, 17, tzinfo=timezone.utc)


class Screen(CustomController):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def connect(self):
        return True

    def request_uuid(self):
        return "special-daily-replay"

    def screencap(self):
        return np.full((720, 1280, 3), 10 + self.state["page"] * 25, dtype=np.uint8)

    def click(self, x, y):
        self.state["actions"].append("UtilsClick")
        self.state["quest_target"] = [x, y]
        self.state["screen"] = "stamina" if self.state["no_stamina"] else "support"
        return True

    def touch_down(self, contact, x, y, pressure):
        return self.click(x, y)

    def touch_up(self, contact):
        return True


class Recognize(CustomRecognition):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def analyze(self, context, argv):
        state = self.state
        name = argv.node_name
        if name == PREFIX + ".Search":
            if state["screen"] == "quests" and state["page"] == state["quest_page"]:
                if any(re.search(p, state["title"]) for p in state["patterns"]):
                    return [700, 310, 360, 55]
            return None
        screens = {
            "Activity.Go": "home",
            PREFIX + ".NoStamina": "stamina",
            PREFIX + ".SupportTab": "support",
            PREFIX + ".SupportSelect": "support",
            "Global.AutoCombat.Start": "team",
            "Global.AutoCombat": "battle",
            "Global.AutoCombat.FirstClear": "first_clear",
            "Global.AutoCombat.BacktoEntry": "bonus",
            "Global.AutoCombat.Back1": "results",
            "Reward.Click": "home",
            "Reward.Get": "missions",
            "Reward.Get1": "reward_dialog",
            "Reward.Back": "missions",
            "Reward.Gift": "home",
        }
        if screens.get(name) == state["screen"]:
            if name == "Activity.Go" and state["entry_missing"]:
                return None
            return [50, 200, 60, 30]
        return None


class Act(CustomAction):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def run(self, context, argv):
        state = self.state
        name = argv.node_name
        state["actions"].append(name)
        if name == "Global.Entry":
            if state["return_fails"] and state["battles"]:
                return False
            state["screen"] = "home"
        elif name == "Activity.Go":
            state["screen"] = "quests"
        elif name == PREFIX + ".ScrollTop":
            state["page"] = max(0, state["page"] - 1)
        elif name == PREFIX + ".ScrollDown":
            state["page"] = min(3, state["page"] + 1)
            if state["cancel_scan"]:
                context.tasker.post_stop()
        elif name == PREFIX + ".SupportSelect":
            state["screen"] = "team"
        elif name == "Global.AutoCombat.Start":
            state["screen"] = "battle"
        elif name == "Global.AutoCombat":
            state["battles"] += 1
            if state["battle_fails"]:
                return False
            state["screen"] = "first_clear" if state["first_clear"] else "results"
        elif name == "Global.AutoCombat.FirstClear":
            state["screen"] = "bonus"
        elif name in ("Global.AutoCombat.BacktoEntry", "Global.AutoCombat.Back1"):
            state["screen"] = "quests"
        elif name == "Reward.Click":
            # A reward action is the first consumer of the parent context after
            # the special battle. Its farming routes must still be intact.
            state["parent_combat"] = context.get_node_data("Global.AutoCombat")
            state["parent_return"] = context.get_node_data("Global.AutoCombat.BacktoEntry")
            state["screen"] = "missions"
        elif name == "Reward.Get":
            state["screen"] = "reward_dialog"
        elif name == "Reward.Get1":
            state["screen"] = "missions"
        elif name == "Reward.Back":
            state["screen"] = "home"
        elif name == "Reward.Gift":
            state["gift"] = True
        return True


class SpecialDailyRewardTests(unittest.TestCase):
    def replay(self, title="10周年記念黄金洞窟", now=ACTIVE_DAY,
               quest_page=0, initial_page=0, enabled=True, use_potion=False, **options):
        state = dict(screen="home", page=initial_page, quest_page=quest_page,
                     title=title, actions=[], battles=0, gift=False, first_clear=False,
                     no_stamina=False, entry_missing=False, battle_fails=False,
                     cancel_scan=False, return_fails=False, available_potions=(),
                     potion_attempts=[], used_potions=[], potion_ack_fails=False,
                     prior_potions=dict(All=0, Half=0, Mini=0, Ranpoil=0))
        state.update(options)
        pipeline = {}
        for filename in ("reward.json", "reward_special_daily.json", "global.json", "startup.json",
                         "Utils.json", "combat/activity.json", "combat/global_combat.json"):
            path = ROOT / "assets/resource/base/pipeline" / filename
            pipeline.update(json.loads(path.read_text(encoding="utf-8")))
        state["patterns"] = pipeline[PREFIX + ".Search"]["recognition"]["param"]["expected"]
        # Device/OCR/battle boundaries are simulated; the production discovery
        # action, cloning, next/on_error and settlement routes run unchanged.
        for name, node in pipeline.items():
            if "recognition" in node:
                node["recognition"] = {"type": "Custom", "param": {"custom_recognition": "Screen"}}
            if "action" in node and name not in (PREFIX + ".Entry", PREFIX + ".Drink", "UtilsClick"):
                node["action"] = {"type": "Custom", "param": {"custom_action": "Act"}}
            node.update(pre_delay=0, post_delay=0, pre_wait_freezes=0,
                        post_wait_freezes=0, timeout=30, rate_limit=1)
        pipeline["Global.Entry"] = {"action": {"type": "Custom", "param": {"custom_action": "Act"}}}
        pipeline["Reward.Gift"]["next"] = []
        pipeline["Global.AutoCombat"]["action"]["param"]["custom_action_param"] = "existing-farming-script"
        pipeline["Global.AutoCombat.BacktoEntry"]["next"] = ["Activity.Select"]
        interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))
        if not enabled:
            choice = next(c for c in interface["option"]["check_special_daily"]["cases"] if c["name"] == "No")
            pipeline["Reward.Entry"].update(choice["pipeline_override"]["Reward.Entry"])
        if use_potion:
            children = next(c for c in interface["option"]["check_special_daily"]["cases"] if c["name"] == "Yes")["option"]
            self.assertEqual(children, ["special_daily_use_AP_potion"])
            choice = next(c for c in interface["option"][children[0]]["cases"] if c["name"] == "Yes")
            for node, override in choice["pipeline_override"].items():
                pipeline[node].update(override)
        shared = NS(combat_set=True, auto_combat_mode=True, leader_pos=[10, 20],
                    IGNORE_LIST=[], drink_times=state["prior_potions"].copy())
        module = load_agent_module("agent/custom/action/special_daily_reward.py", info_share=shared)
        module.logger.exception.side_effect = lambda *args: state.update(error=traceback.format_exc())
        drink_module = load_agent_module(
            "agent/custom/action/combat_drink.py", info_share=shared,
            proj_path=NS(AUTO_COMBAT_DIR="unused"), act_mgr=Mock(detect_lang=Mock(return_value="cn")),
        )
        drink_action = drink_module.CombatDrink()

        def use_item(context, item, limits, markers):
            state["potion_attempts"].append(item)
            if item not in state["available_potions"] or limits.get(item, 0) <= drink_action.drink_times[item]:
                return False
            drink_action._record_use(item)
            state["used_potions"].append(item)
            if state["potion_ack_fails"]:
                return False
            state["screen"] = "support"
            return True

        # Only the item-confirmation boundary is simulated. The real drink
        # action chooses the priority, allowance and single-consumption stop.
        drink_action.drink = Mock(side_effect=use_item)
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pipeline").mkdir()
            (bundle / "pipeline/replay.json").write_text(json.dumps(pipeline), encoding="utf-8")
            resource = Resource()
            resource.register_custom_recognition("Screen", Recognize(state))
            resource.register_custom_action("Act", Act(state))
            resource.register_custom_action("SpecialDailyReward", module.SpecialDailyReward())
            resource.register_custom_action("CombatDrink", drink_action)
            self.assertTrue(resource.post_bundle(bundle).wait().status.succeeded)
            controller = Screen(state)
            self.assertTrue(controller.post_connection().wait().status.succeeded)
            tasker = Tasker()
            self.assertTrue(tasker.bind(resource, controller))
            expired = threading.Event()

            def stop():
                expired.set()
                tasker.post_stop()

            timer = threading.Timer(10, stop)
            timer.start()
            try:
                with patch.object(module, "datetime") as clock:
                    clock.now.return_value = now
                    clock.fromisoformat.side_effect = datetime.fromisoformat
                    success = tasker.post_task("Reward.Entry").wait().status.succeeded
            finally:
                timer.cancel()
            self.assertFalse(expired.is_set(), state["actions"])
        state["logs"] = "\n".join(str(call) for call in module.logger.method_calls)
        return state, success

    def test_each_daily_quest_runs_once_then_claims_missions_and_gifts(self):
        for title in ("10周年記念黄金洞窟", "10周年記念特別授業"):
            with self.subTest(title=title):
                state, success = self.replay(title)
                self.assertTrue(success, state)
                self.assertEqual(state["battles"], 1)
                self.assertTrue(state["gift"])
                self.assertTrue(700 <= state["quest_target"][0] < 1060)
                self.assertTrue(310 <= state["quest_target"][1] < 365)
                self.assertLess(state["actions"].index("Global.AutoCombat"), state["actions"].index("Reward.Click"))
                self.assertNotIn("Global.AutoCombat.Replay", state["actions"])
                self.assertIn("已完成并结算", state["logs"])

    def test_scrolls_in_both_directions_to_find_the_daily_entry(self):
        for initial_page, quest_page in ((0, 3), (3, 0)):
            with self.subTest(initial_page=initial_page):
                state, success = self.replay(initial_page=initial_page, quest_page=quest_page)
                self.assertTrue(success, state)
                self.assertEqual(state["battles"], 1)
                self.assertTrue(state["gift"])

    def test_absent_daily_and_other_anniversary_quests_only_claim_rewards(self):
        for title in ("", "黄金洞窟", "10周年の挙式場", "等级经验值的登龙门"):
            with self.subTest(title=title):
                state, success = self.replay(title)
                self.assertTrue(success, state)
                self.assertEqual(state["battles"], 0)
                self.assertTrue(state["gift"])
                self.assertIn("未发现", state["logs"])
                self.assertNotIn("已完成并结算", state["logs"])

    def test_first_clear_settles_without_selecting_another_quest(self):
        state, success = self.replay(first_clear=True)
        self.assertTrue(success, state)
        self.assertEqual(state["battles"], 1)
        self.assertTrue(state["gift"])
        self.assertIn("Global.AutoCombat.FirstClear", state["actions"])
        self.assertIn("Global.AutoCombat.BacktoEntry", state["actions"])
        self.assertNotIn("Activity.Select", state["actions"])

    def test_insufficient_stamina_and_unavailable_event_continue_claiming(self):
        for option in ("no_stamina", "entry_missing"):
            with self.subTest(option=option):
                state, success = self.replay(**{option: True})
                self.assertTrue(success, state)
                self.assertEqual(state["battles"], 0)
                self.assertTrue(state["gift"])
                self.assertNotIn("已完成并结算", state["logs"])
                self.assertNotIn("Global.AutoCombat.PreDrink", state["actions"])

    def test_event_window_uses_japan_time_and_excludes_the_end(self):
        cases = (
            ("2026-11-13T14:59:59+00:00", 0),
            ("2026-11-13T15:00:00+00:00", 1),
            ("2026-12-03T14:59:59+00:00", 1),
            ("2026-12-03T15:00:00+00:00", 0),
        )
        for timestamp, count in cases:
            with self.subTest(timestamp=timestamp):
                state, success = self.replay(now=datetime.fromisoformat(timestamp))
                self.assertTrue(success, state)
                self.assertEqual(state["battles"], count)
                self.assertTrue(state["gift"])
                if not count:
                    self.assertNotIn("Activity.Go", state["actions"])

    def test_disabled_check_claims_rewards_directly(self):
        state, success = self.replay(enabled=False, use_potion=True, no_stamina=True,
                                     available_potions=("Mini",))
        self.assertTrue(success, state)
        self.assertTrue(state["gift"])
        self.assertNotIn("Activity.Go", state["actions"])
        self.assertEqual(state["used_potions"], [])

    def test_potion_option_uses_small_then_medium_then_large(self):
        for available, attempts in (
            (("Mini", "Half", "All"), ["Mini"]),
            (("Half", "All"), ["Mini", "Half"]),
            (("All",), ["Mini", "Half", "All"]),
        ):
            with self.subTest(available=available):
                state, success = self.replay(no_stamina=True, use_potion=True, available_potions=available)
                self.assertTrue(success, state)
                self.assertEqual(state["potion_attempts"], attempts)
                self.assertEqual(state["used_potions"], [attempts[-1]])
                self.assertEqual(state["battles"], 1)
                self.assertTrue(state["gift"])
                self.assertIn("已完成并结算", state["logs"])
                self.assertNotIn("本次未补足体力", state["logs"])

    def test_potion_option_does_not_consume_when_stamina_is_sufficient_or_disabled(self):
        for no_stamina, use_potion in ((False, True), (True, False)):
            with self.subTest(no_stamina=no_stamina):
                state, success = self.replay(no_stamina=no_stamina, use_potion=use_potion,
                                             available_potions=("Mini", "Half", "All"))
                self.assertTrue(success, state)
                self.assertEqual(state["used_potions"], [])
                self.assertEqual(state["battles"], 0 if no_stamina else 1)
                self.assertTrue(state["gift"])

    def test_no_available_potion_continues_claiming(self):
        state, success = self.replay(no_stamina=True, use_potion=True)
        self.assertTrue(success, state)
        self.assertEqual(state["potion_attempts"], ["Mini", "Half", "All"])
        self.assertEqual(state["used_potions"], [])
        self.assertEqual(state["battles"], 0)
        self.assertTrue(state["gift"])

    def test_previous_farming_consumption_does_not_exhaust_anniversary_allowance(self):
        state, success = self.replay(no_stamina=True, use_potion=True, available_potions=("Mini",),
                                     prior_potions=dict(All=2, Half=3, Mini=4, Ranpoil=0))
        self.assertTrue(success, state)
        self.assertEqual(state["used_potions"], ["Mini"])
        self.assertEqual(state["battles"], 1)
        self.assertTrue(state["gift"])

    def test_unconfirmed_potion_consumption_does_not_try_larger_potions(self):
        state, success = self.replay(no_stamina=True, use_potion=True, potion_ack_fails=True,
                                     available_potions=("Mini", "Half", "All"))
        self.assertTrue(success, state)
        self.assertEqual(state["potion_attempts"], ["Mini"])
        self.assertEqual(state["used_potions"], ["Mini"])
        self.assertEqual(state["battles"], 0)
        self.assertTrue(state["gift"])

    def test_farming_script_and_return_route_survive_scoped_battle(self):
        state, success = self.replay()
        self.assertTrue(success, state)
        combat = state["parent_combat"]
        self.assertEqual(combat["action"]["param"]["custom_action_param"], "existing-farming-script")
        self.assertEqual([node["name"] for node in combat["next"]], ["Global.AutoCombat.Count"])
        self.assertEqual([node["name"] for node in state["parent_return"]["next"]], ["Activity.Select"])

    def test_failed_battle_is_not_reported_as_completed(self):
        state, success = self.replay(battle_fails=True)
        self.assertFalse(success, state)
        self.assertEqual(state["battles"], 1)
        self.assertFalse(state["gift"])
        self.assertNotIn("已完成并结算", state["logs"])
        self.assertNotIn("Global.AutoCombat.Replay", state["actions"])

    def test_cancel_during_search_does_not_start_combat_or_claim(self):
        state, success = self.replay(title="", cancel_scan=True)
        self.assertFalse(success, state)
        self.assertEqual(state["battles"], 0)
        self.assertFalse(state["gift"])

    def test_unfinished_return_is_not_reported_as_completed(self):
        state, success = self.replay(return_fails=True)
        self.assertFalse(success, state)
        self.assertEqual(state["battles"], 1)
        self.assertFalse(state["gift"])
        self.assertNotIn("已完成并结算", state["logs"])


if __name__ == "__main__":
    unittest.main()
