"""Exercise language detection through the potion and persisted weekly-task consumers."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from agent_modules import load_agent_module


class LanguageConsumerTests(unittest.TestCase):
    def setUp(self):
        self.shared = SimpleNamespace(current_lang="", IGNORE_LIST=[], show_support=False,
                                      drink_times=dict(All=0, Half=0, Mini=0, Ranpoil=0))
        self.helper = load_agent_module("agent/utils/action_helpers.py", info_share=self.shared)

    def potion(self, previous, title=None):
        self.shared.current_lang = previous
        module = load_agent_module(
            "agent/custom/action/combat_drink.py", info_share=self.shared,
            act_mgr=self.helper.act_mgr, proj_path=SimpleNamespace(AUTO_COMBAT_DIR="unused"),
        )
        context = Mock()

        def recognize(entry, image, pipeline_override):
            x, y, width, height = pipeline_override[entry]["recognition"]["param"]["roi"]
            texts = ["X1", "×3", "X1"]
            if title and x <= 32 < x + width and y <= 45 < y + height:
                texts.append(title)
            results = [SimpleNamespace(text=text) for text in texts]
            return SimpleNamespace(best_result=results[0], filtered_results=results)

        context.run_recognition.side_effect = recognize
        # No allowed medicine: the real action must exit using the correct language.
        succeeded = module.CombatDrink().run(context, SimpleNamespace(
            node_name="Global.AutoCombat.Drink1", custom_action_param='{}'))
        self.assertFalse(succeeded)
        return context

    def test_quantity_only_panel_exits_using_known_chinese(self):
        context = self.potion(previous="cn")
        param = context.run_task.call_args.kwargs["pipeline_override"]["UtilsOCR"]["recognition"]["param"]
        self.assertEqual(param["text"], "返回")
        self.assertEqual(self.shared.current_lang, "cn")

    def test_first_potion_panel_uses_header_to_identify_language(self):
        for title, language, back in [("体力恢复", "cn", "返回"), ("體力恢復", "tw", "返回"),
                                      ("スタミナ回復", "jp", "戻る"), ("Back", "en", "Back")]:
            with self.subTest(language=language):
                context = self.potion(previous="", title=title)
                param = context.run_task.call_args.kwargs["pipeline_override"]["UtilsOCR"]["recognition"]["param"]
                self.assertEqual(param["text"], back)
                self.assertEqual(self.shared.current_lang, language)

    def test_unknown_language_does_not_use_guessed_potion_buttons(self):
        context = self.potion(previous="")
        context.run_task.assert_not_called()

    def test_unknown_language_does_not_overwrite_weekly_state(self):
        for node in ("CheckWeeklyMissions.Record", "CheckWeeklyMissions.AllCompleted"):
            with self.subTest(node=node):
                module = load_agent_module("agent/custom/action/weekly_mission.py", info_share=self.shared,
                                           act_mgr=Mock(detect_lang=Mock(return_value="")))
                action = module.WeeklyMission()
                action._load_mission_data = Mock(return_value={})
                self.assertFalse(action.run(Mock(), SimpleNamespace(node_name=node)))
                module.data_io.write_app_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
