"""Regressions for F01-F06 and F08 (F07 OCR waits are intentionally deferred)."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from maa.define import MaaStatusEnum, Status, TaskDetail
from agent_modules import load_agent_module


def task_result(success):
    return TaskDetail(1, "UtilsOCR", [], Status(MaaStatusEnum.succeeded if success else MaaStatusEnum.failed))


def state(**kwargs):
    values = dict(current_lang="cn", IGNORE_LIST=[], show_support=False, combat_set=True,
                  auto_combat_mode=True, leader_pos=[], drink_times=dict(All=0, Half=0, Mini=0, Ranpoil=0))
    values.update(kwargs)
    return NS(**values)


def context():
    ctx = Mock()
    ctx.tasker.stopping = False
    ctx.run_action.return_value = NS(success=True)
    ctx.run_task.return_value = task_result(True)
    return ctx


def ocr(*texts):
    results = [NS(text=text, box=[516 + i * 180, 180, 160, 30], score=1) for i, text in enumerate(texts)]
    return NS(best_result=results[0] if results else None, all_results=results, filtered_results=results)


class TaskResultTests(unittest.TestCase):
    def setUp(self):
        self.module = load_agent_module("agent/utils/action_helpers.py")

    def test_filter_stops_at_each_failed_required_step(self):
        # Open, reset, attribute template, and final confirm must all succeed.
        self.module.act_mgr.UI_DATA = {"element": {"fire": "fire.png"}}
        with patch.object(self.module.act_mgr, "detect_lang", return_value="cn"), \
             patch.object(self.module.act_mgr, "normalize_template_path", side_effect=lambda p: p):
            for failure in range(4):
                with self.subTest(step=failure):
                    ctx = context()
                    ctx.run_task.side_effect = [task_result(True)] * failure + [task_result(False)] + [task_result(True)] * 5
                    self.assertFalse(self.module.act_mgr.choose_filter(ctx, element="fire"))
                    self.assertEqual(ctx.run_task.call_count, failure + 1)

    def test_successful_filter_remains_successful(self):
        with patch.object(self.module.act_mgr, "detect_lang", return_value="cn"):
            self.assertTrue(self.module.act_mgr.choose_filter(context()))


class BattleFailureTests(unittest.TestCase):
    def setUp(self):
        self.shared = state()
        self.helper = load_agent_module("agent/utils/action_helpers.py", info_share=self.shared)
        self.module = load_agent_module("agent/custom/action/auto_combat.py", info_share=self.shared,
                                        act_mgr=self.helper.act_mgr, proj_path=NS(AUTO_COMBAT_DIR="unused"))
        self.action = self.module.AutoCombat()
        self.ctx = context()
        self.argv = NS(node_name="Global.AutoCombat", custom_action_param="")
        self.ctx.run_recognition.return_value = ocr()

    def run_battle(self):
        with patch.object(self.module.time, "sleep"), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.action.run(self.ctx, self.argv)

    def script(self, loop=False):
        self.shared.auto_combat_mode = False
        self.argv.custom_action_param = "script"
        action = {"loop": {"0": {"char": 1, "action": ["S"]}}} if loop else {"0": {"char": 1, "action": ["S"]}}
        self.module.data_io.find_target_files.return_value = {"fight": {"pos": {"1": [0, 0]}, "action": action}}

    def test_missing_leader_after_previous_battle_returns_failure(self):
        self.script()
        self.shared.leader_pos = [700, 500]
        self.assertFalse(self.run_battle())

    def test_missing_leader_during_position_recheck_returns_failure(self):
        self.script()
        self.shared.leader_pos = [700, 500]
        self.action._get_posL = Mock(side_effect=[[810, 500], None])
        self.assertFalse(self.run_battle())

    def test_automatic_battle_recognition_error_is_failure(self):
        self.ctx.run_recognition.return_value = None
        self.assertFalse(self.run_battle())

    def test_script_recognition_error_is_failure(self):
        self.script()
        self.action._get_posL = Mock(return_value=[700, 500])
        self.ctx.run_recognition.return_value = None
        self.assertFalse(self.run_battle())

    def test_loop_recognition_error_is_failure(self):
        self.script(loop=True)
        self.action._get_posL = Mock(return_value=[700, 500])
        self.ctx.run_recognition.return_value = None
        self.assertFalse(self.run_battle())

    def test_normal_results_screen_is_success(self):
        self.ctx.run_recognition.side_effect = [ocr(), ocr("再次挑战")]
        self.assertTrue(self.run_battle())

    def test_failed_menu_does_not_set_combat_options(self):
        self.shared.combat_set = False
        self.shared.auto_combat_mode = False
        self.ctx.run_task.return_value = task_result(False)
        self.ctx.run_recognition.side_effect = [ocr("OFF"), ocr(), ocr("再次挑战")]
        self.assertFalse(self.run_battle())
        self.assertFalse(self.shared.combat_set)

    def test_cancelled_script_does_not_report_completion(self):
        self.script()
        self.action._get_posL = Mock(return_value=[700, 500])
        self.ctx.tasker.stopping = True
        self.assertFalse(self.run_battle())


class CommunityResultTests(unittest.TestCase):
    def setUp(self):
        helper = load_agent_module("agent/utils/action_helpers.py")
        self.helper = helper.act_mgr
        module = load_agent_module("agent/custom/action/formation.py", act_mgr=self.helper,
                                   proj_path=NS(AUTO_COMBAT_DIR="unused", CHAR_FILE="unused",
                                                CHAR_LOWSTAR_FILE="unused", AR_FILE="unused", UI_FILE="unused"))
        self.action = module.Formation()
        self.action._get_community_template_path = Mock(return_value="guild.png")
        self.ctx = context()

    def select(self):
        with patch.object(self.helper, "detect_lang", return_value="cn"):
            return self.action._select_community(self.ctx, "guild")

    def test_missing_first_page_continues_to_second_page(self):
        self.ctx.run_task.side_effect = [task_result(True), task_result(False), task_result(True), task_result(True)]
        self.assertTrue(self.select())
        self.assertEqual(self.ctx.run_action.call_count, 1)

    def test_missing_community_is_bounded_failure(self):
        self.ctx.run_task.side_effect = [task_result(True)] + [task_result(False)] * 12
        self.assertFalse(self.select())
        self.assertEqual(self.ctx.run_task.call_count, 13)

    def test_enter_failure_does_not_search(self):
        self.ctx.run_task.return_value = task_result(False)
        self.assertFalse(self.select())
        self.assertEqual(self.ctx.run_task.call_count, 1)

    def test_confirm_failure_is_not_success(self):
        self.ctx.run_task.side_effect = [task_result(True), task_result(True), task_result(False)]
        self.assertFalse(self.select())


class WeeklyStateTests(unittest.TestCase):
    def setUp(self):
        self.shared = state()
        self.helper = load_agent_module("agent/utils/action_helpers.py", info_share=self.shared)
        self.module = load_agent_module("agent/custom/action/weekly_mission.py", info_share=self.shared, act_mgr=self.helper.act_mgr)
        self.action = self.module.WeeklyMission()
        self.saved = deepcopy(self.action.CN_MISSION)
        self.module.data_io.read_app_state.side_effect = lambda *args: deepcopy(self.saved)
        self.ctx = context()

    def record(self, language="cn"):
        original = self.helper.act_mgr.detect_lang
        def detect(*args, **kwargs):
            return original(*args, **kwargs) if kwargs.get("compare_list") is not None else language
        with patch.object(self.module.time, "sleep"), redirect_stdout(io.StringIO()), \
             patch.object(self.helper.act_mgr, "detect_lang", side_effect=detect):
            return self.action.run(self.ctx, NS(node_name="CheckWeeklyMissions.Record"))

    def test_empty_ocr_does_not_write_completed_records(self):
        self.ctx.run_recognition.return_value = ocr()
        self.assertFalse(self.record())
        self.module.data_io.write_app_state.assert_not_called()
        self.assertFalse(self.shared.show_support)

    def test_valid_progress_preserves_unseen_tasks(self):
        self.ctx.run_recognition.return_value = ocr("完成攻略3次地城", "1/3")
        self.assertTrue(self.record())
        written = self.module.data_io.write_app_state.call_args.args[1]
        self.assertEqual(written["完成攻略3次地城"]["current"], 1)
        self.assertFalse(written["累计消耗450点体力"]["completed"])

    def test_failed_swipe_does_not_write_partial_scan(self):
        self.ctx.run_recognition.return_value = ocr("完成攻略3次地城", "1/3")
        self.ctx.run_action.return_value = NS(success=False)
        self.assertFalse(self.record())
        self.module.data_io.write_app_state.assert_not_called()

    def test_language_migration_uses_current_screen_language(self):
        self.saved = deepcopy(self.action.EN_MISSION)
        self.ctx.run_recognition.return_value = ocr("完成攻略3次地城", "1/3")
        self.assertTrue(self.record())
        written = self.module.data_io.write_app_state.call_args.args[1]
        self.assertIn("完成攻略3次地城", written)
        self.assertNotIn("Clear 3 dungeon quests", written)
        self.assertEqual(self.shared.current_lang, "cn")

    def test_classifying_saved_text_does_not_change_screen_language(self):
        result = self.helper.act_mgr.detect_lang(None, [0, 0, 0, 0], compare_list=list(self.action.EN_MISSION))
        self.assertEqual(result, "en")
        self.assertEqual(self.shared.current_lang, "cn")

    def test_explicit_all_completed_node_still_completes_tasks(self):
        with patch.object(self.helper.act_mgr, "detect_lang", return_value="cn"):
            self.assertTrue(self.action.run(self.ctx, NS(node_name="CheckWeeklyMissions.AllCompleted")))
        self.assertTrue(all(v["completed"] for v in self.module.data_io.write_app_state.call_args.args[1].values()))

    def test_language_migration_preserves_saved_progress(self):
        self.saved = deepcopy(self.action.EN_MISSION)
        self.saved["Use 450 stamina points"]["current"] = 210
        self.ctx.run_recognition.return_value = ocr("完成攻略3次地城", "1/3")
        self.assertTrue(self.record())
        written = self.module.data_io.write_app_state.call_args.args[1]
        self.assertEqual(written["累计消耗450点体力"]["current"], 210)

    def test_empty_frame_after_valid_page_does_not_write_partial_scan(self):
        self.ctx.run_recognition.side_effect = [ocr("完成攻略3次地城", "1/3"), ocr(), ocr(), ocr()]
        self.assertFalse(self.record())
        self.module.data_io.write_app_state.assert_not_called()

    def test_transient_empty_frame_can_recover(self):
        self.ctx.run_recognition.side_effect = [ocr(), ocr("完成攻略3次地城", "1/3"), ocr("完成攻略3次地城", "1/3")]
        self.assertTrue(self.record())


class PotionLimitTests(unittest.TestCase):
    def setUp(self):
        self.shared = state()
        self.helper = load_agent_module("agent/utils/action_helpers.py", info_share=self.shared)
        self.module = load_agent_module("agent/custom/action/combat_drink.py", info_share=self.shared,
                                        act_mgr=self.helper.act_mgr, proj_path=NS(AUTO_COMBAT_DIR="unused"))
        self.action = self.module.CombatDrink()
        self.ctx = context()

    def test_dp_unconfirmed_request_cannot_repeat_past_limit(self):
        self.ctx.run_recognition.side_effect = lambda *a, **kw: ocr("DP") if kw["pipeline_override"][a[0]]["recognition"]["param"].get("text") == "DP" else ocr()
        with patch.object(self.module.time, "sleep"), redirect_stdout(io.StringIO()):
            first = self.action.drink(self.ctx, "Ranpoil", {"Ranpoil": 1}, ["确定", "返回"])
            second = self.action.drink(self.ctx, "Ranpoil", {"Ranpoil": 1}, ["确定", "返回"])
        self.assertFalse(first)
        self.assertFalse(second)
        self.assertEqual(self.ctx.run_action.call_count, 1)
        self.assertEqual(self.shared.drink_times["Ranpoil"], 1)

    def test_failed_item_click_is_not_success(self):
        self.ctx.run_recognition.return_value = ocr("DP")
        self.ctx.run_action.return_value = NS(success=False)
        self.assertFalse(self.action.drink(self.ctx, "Ranpoil", {"Ranpoil": 1}, ["确定", "返回"]))

    def test_failed_confirmation_does_not_report_recovery(self):
        self.ctx.run_recognition.side_effect = [ocr("potion"), ocr("确定")]
        self.ctx.run_task.return_value = task_result(False)
        self.assertFalse(self.action.drink(self.ctx, "All", {"All": 1}, ["确定", "返回"]))

    def test_confirmed_potion_counts_once(self):
        self.ctx.run_recognition.side_effect = [ocr("potion"), ocr("确定")]
        self.assertTrue(self.action.drink(self.ctx, "All", {"All": 1}, ["确定", "返回"]))
        self.assertEqual(self.shared.drink_times["All"], 1)

    def test_confirmed_dp_counts_once(self):
        self.ctx.run_recognition.side_effect = [ocr("DP"), ocr("确定")]
        self.assertTrue(self.action.drink(self.ctx, "Ranpoil", {"Ranpoil": 1}, ["确定", "返回"]))
        self.assertEqual(self.shared.drink_times["Ranpoil"], 1)

    def test_dp_without_confirmation_requires_visible_transition(self):
        dp_selected = False
        def recognize(entry, image, pipeline_override):
            nonlocal dp_selected
            text = pipeline_override[entry]["recognition"]["param"].get("text")
            if text == "DP" and not dp_selected:
                dp_selected = True
                return ocr("DP")
            return ocr("LOADING") if text == "LOADING" else ocr()
        self.ctx.run_recognition.side_effect = recognize
        with patch.object(self.module.time, "sleep"):
            self.assertTrue(self.action.drink(self.ctx, "Ranpoil", {"Ranpoil": 1}, ["确定", "返回"]))
            self.assertFalse(self.action.drink(self.ctx, "Ranpoil", {"Ranpoil": 1}, ["确定", "返回"]))
        self.assertEqual(self.ctx.run_action.call_count, 1)
        self.assertEqual(self.shared.drink_times["Ranpoil"], 1)


class DefaultSupportTests(unittest.TestCase):
    def setUp(self):
        self.shared = state(select_support_fast=False)
        self.helper = load_agent_module("agent/utils/action_helpers.py", info_share=self.shared)
        self.module = load_agent_module("agent/custom/action/select_support.py", info_share=self.shared,
                                        act_mgr=self.helper.act_mgr,
                                        proj_path=NS(AUTO_COMBAT_DIR="unused", UI_FILE="unused", CHAR_FILE="unused", IMAGE_DIR=Path("unused")))

    def test_empty_configuration_reaches_default_scanning(self):
        action = self.module.SelectSupport()
        action._scan_and_select_support = Mock(return_value=False)
        self.assertFalse(action.run(context(), NS(node_name="SelectSupport", custom_action_param="{}")))
        self.assertEqual(action._scan_and_select_support.call_args.args[2], [])

    def test_default_scan_can_choose_a_recognized_support(self):
        action = self.module.SelectSupport()
        ctx = context()
        result = {"any": {"01": {"res_1": {"box": [100, 200, 40, 40], "Level": "80", "ATK": "9000"}}}}
        ctx.run_recognition.return_value = NS(box=[100, 200, 40, 40], best_result=NS(detail=result))
        self.module.match_mgr.group_info.side_effect = [(["first"], [[45, 190, 400, 150]]), (["first"], [[45, 190, 400, 150]])]
        self.module.match_mgr.merge_res_dicts.side_effect = lambda old, new: {**old, **new}
        self.assertTrue(action._scan_and_select_support(ctx, None, [], "best", [45, 190, 400, 530]))


if __name__ == "__main__":
    unittest.main()
