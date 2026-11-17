"""Exercise potion ordering and the native recognition-box input contract."""

import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from maa.define import Rect
from agent_modules import load_agent_module


class CombatDrinkPriorityTests(unittest.TestCase):
    def setUp(self):
        self.shared = NS(IGNORE_LIST=[], drink_times=dict(All=0, Half=0, Mini=0, Ranpoil=0))
        self.module = load_agent_module(
            "agent/custom/action/combat_drink.py", info_share=self.shared,
            proj_path=NS(AUTO_COMBAT_DIR="unused"), act_mgr=Mock(
                detect_lang=Mock(return_value="cn"), task_succeeded=lambda task: task.status.succeeded),
        )
        self.action = self.module.CombatDrink()
        self.context = Mock()
        self.context.tasker.stopping = False

    def test_normal_combat_keeps_its_existing_potion_order(self):
        self.action.drink = Mock(return_value=False)
        self.assertFalse(self.action.run(self.context, NS(
            node_name="Global.AutoCombat.Drink1", custom_action_param="{}")))
        self.assertEqual([call.args[1] for call in self.action.drink.call_args_list],
                         ["All", "Half", "Mini", "Ranpoil"])

    def test_native_boxes_and_unconfirmed_use_stop_after_the_small_potion(self):
        def dispatch(entry, box, pipeline_override):
            # Maa serializes pipeline overrides before dispatching the input.
            json.dumps(pipeline_override)
            return NS(success=True)

        self.context.run_action.side_effect = dispatch
        self.context.run_recognition.side_effect = [
            NS(best_result=NS(box=Rect(500, 200, 150, 80))),
            NS(best_result=NS(box=Rect(540, 400, 100, 40), text="确定")),
        ]
        self.context.run_task.return_value = NS(status=NS(succeeded=False))
        self.assertFalse(self.action.run(self.context, NS(
            node_name="Reward.SpecialDaily.Drink",
            custom_action_param=json.dumps({"priority": ["Mini", "Half", "All"], "use_once": True}))))
        self.assertEqual(self.shared.drink_times, dict(All=0, Half=0, Mini=1, Ranpoil=0))
        self.assertEqual(self.context.run_action.call_count, 2)
        self.assertEqual(self.context.run_recognition.call_count, 2)

    def test_cancelled_task_does_not_attempt_potion_use(self):
        self.context.tasker.stopping = True
        self.action.drink = Mock(return_value=True)
        self.assertFalse(self.action.run(self.context, NS(
            node_name="Reward.SpecialDaily.Drink",
            custom_action_param=json.dumps({"priority": ["Mini", "Half", "All"], "use_once": True}))))
        self.action.drink.assert_not_called()


if __name__ == "__main__":
    unittest.main()
