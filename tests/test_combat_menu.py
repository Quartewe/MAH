"""Battle setup must observe UI transitions, including ignored MENU clicks."""
import re
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from agent_modules import load_agent_module
from test_review_fixes import context, state, task_result


class CombatMenuTests(unittest.TestCase):
    def setUp(self):
        self.shared = state(combat_set=False, auto_combat_mode=False)
        helper = load_agent_module('agent/utils/action_helpers.py', info_share=self.shared)
        self.module = load_agent_module('agent/custom/action/auto_combat.py',
            info_share=self.shared, act_mgr=helper.act_mgr,
            proj_path=NS(AUTO_COMBAT_DIR='unused'))
        self.action = self.module.AutoCombat()
        self.ctx = context()
        self.scene = 'battle'
        self.options = ['ON', 'ON', 'ON']
        self.menu_attempts = 0
        self.ignore_menu = 1
        self.ignore_back = 0
        self.clicks = []
        self.auto = 'OFF'
        self.now = 0
        self.ctx.run_recognition.side_effect = self.recognize
        self.ctx.run_action.side_effect = self.click
        self.ctx.run_task.side_effect = self.legacy_task
        self.action._detect_complete = Mock(side_effect=self.complete)

    def complete(self, ctx):
        self.action.if_complete = True
        return True

    def recognize(self, name, image, pipeline_override):
        if name != 'UtilsOCR':
            return NS(best_result=None, filtered_results=[])
        param = pipeline_override[name]['recognition']['param']
        expected = param.get('expected', [''])
        expected = [expected] if isinstance(expected, str) else expected
        roi = param.get('roi', [0, 0, 1280, 720])
        # Positions match the separately captured real 1280x720 screenshots.
        values = [('MENU', [30, 16, 80, 30])]
        if self.scene == 'battle':
            values += [(self.auto, [402, 35, 28, 19]), ('アラクシア', [330, 80, 290, 20])]
        else:
            values += [('设定', [583, 86, 49, 28]), ('返回', [1115, 101, 59, 29])]
            if self.scene == 'settings':
                values += [(v, [184, 235 + i * 113, 40, 30]) for i, v in enumerate(self.options)]
        result = [NS(text=text, box=box, score=1) for text, box in values
                  if roi[0] <= box[0] < roi[0] + roi[2] and roi[1] <= box[1] < roi[1] + roi[3]
                  and any(re.search(e, text) for e in expected)]
        return NS(best_result=result[0] if result else None, filtered_results=result, all_results=result)

    def click(self, name, box=None, pipeline_override=None):
        target = pipeline_override[name]['action']['param']['target']
        x, y = target[:2]
        self.clicks.append((x, y))
        if x < 120 and y < 60:
            self.menu_attempts += 1
            if self.menu_attempts > self.ignore_menu:
                self.scene = 'menu'
        elif x > 1000:
            if self.ignore_back:
                self.ignore_back -= 1
            else:
                self.scene = 'battle'
        elif 500 < x < 750:
            self.scene = 'settings'
        elif 170 < x < 240:
            i = round((y - 235) / 113)
            self.options[i] = 'ON' if self.options[i] == 'OFF' else 'OFF'
        elif 390 < x < 440:
            self.auto = 'ON'
        return NS(success=True)

    def legacy_task(self, name, pipeline_override):
        result = self.recognize(name, None, pipeline_override)
        if not result.best_result:
            return task_result(False)
        self.click('UtilsClick', pipeline_override={'UtilsClick': {'action': {'param': {'target': result.best_result.box}}}})
        return task_result(True)

    def sleep(self, seconds):
        self.now += seconds

    def run_battle(self):
        with patch.object(self.module.time, 'monotonic', side_effect=lambda: self.now), \
             patch.object(self.module.time, 'sleep', side_effect=self.sleep):
            return self.action.run(self.ctx, NS(node_name='Global.AutoCombat', custom_action_param=''))

    def test_ignored_menu_click_retries_then_reaches_native_auto(self):
        self.assertTrue(self.run_battle())
        self.assertEqual(self.menu_attempts, 2)
        self.assertEqual(self.auto, 'ON')
        self.assertTrue(self.shared.combat_set)

    def test_already_open_settings_with_all_on_needs_no_menu_or_tab_click(self):
        self.scene = 'settings'
        self.assertTrue(self.run_battle())
        self.assertEqual(self.menu_attempts, 0)
        self.assertFalse(any(500 < x < 750 for x, _ in self.clicks))

    def test_mixed_options_are_confirmed_on_before_leaving(self):
        self.scene = 'settings'
        self.options = ['OFF', 'ON', 'OFF']
        self.assertTrue(self.run_battle())
        self.assertEqual(self.options, ['ON', 'ON', 'ON'])
        self.assertEqual(sum(170 < x < 240 for x, _ in self.clicks), 2)

    def test_ignored_back_click_is_verified_and_retried(self):
        self.scene = 'settings'
        self.ignore_back = 1
        self.assertTrue(self.run_battle())
        self.assertEqual(sum(x > 1000 for x, _ in self.clicks), 2)

    def test_permanently_ignored_menu_is_bounded_failure(self):
        self.ignore_menu = 10000
        self.assertFalse(self.run_battle())
        self.assertLessEqual(self.now, 60)
        self.assertGreater(self.menu_attempts, 1)
        self.assertFalse(self.shared.combat_set)
        self.assertEqual(self.auto, 'OFF')

    def test_cancel_during_retry_stops_before_another_click(self):
        original = self.sleep
        def cancel(seconds):
            original(seconds)
            self.ctx.tasker.stopping = True
        self.sleep = cancel
        self.assertFalse(self.run_battle())
        self.assertEqual(self.menu_attempts, 1)
        self.assertFalse(self.shared.combat_set)

    def test_failed_capture_cannot_use_cached_menu(self):
        self.scene = 'settings'
        self.ctx.tasker.controller.post_screencap.return_value.wait.return_value.succeeded = False
        self.assertFalse(self.run_battle())
        self.assertEqual(self.clicks, [])

    def test_partial_settings_never_counts_as_ready(self):
        self.scene = 'settings'
        self.options = ['ON', 'ON']
        self.assertFalse(self.run_battle())
        self.assertFalse(self.shared.combat_set)
        self.assertFalse(any(x > 1000 for x, _ in self.clicks))


if __name__ == '__main__':
    unittest.main()
