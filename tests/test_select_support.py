"""Issue #4: no-match selection must not poison later action invocations."""

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from agent_modules import ROOT, load_agent_module


def load_timeout():
    # Use the real shared timer without importing the runtime logger/config.
    logger_module = ModuleType("support_test_utils.logger")
    logger_module.logger = Mock()
    spec = importlib.util.spec_from_file_location(
        "support_test_utils.timeout", ROOT / "agent/utils/timeout.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"support_test_utils.logger": logger_module}):
        spec.loader.exec_module(module)
    return module


class SelectSupportTests(unittest.TestCase):
    def setUp(self):
        self.timeout = load_timeout()
        self.shared = NS(select_support_fast=True)
        helper = load_agent_module("agent/utils/action_helpers.py", info_share=self.shared)
        self.module = load_agent_module(
            "agent/custom/action/select_support.py", info_share=self.shared,
            act_mgr=helper.act_mgr, timeout_mgr=self.timeout.timeout_mgr,
            proj_path=NS(AUTO_COMBAT_DIR="unused", UI_FILE="unused",
                         CHAR_FILE="unused", IMAGE_DIR=Path("unused")))
        self.module.match_mgr.group_info.return_value = (["first"], [[45, 190, 400, 150]])
        self.module.match_mgr.merge_res_dicts.side_effect = lambda old, new: {**old, **new}
        self.action = self.module.SelectSupport()
        self.ctx = Mock()
        self.miss = NS(box=None, best_result=None)
        self.ctx.run_recognition.return_value = self.miss
        self.argv = NS(node_name="Global.AutoCombat.SelectSupport", custom_action_param=json.dumps({
            "ATK": "", "HP": "", "Level": "", "Skill": "", "name": "", "id": 0}))

    def run_at(self, now):
        with patch.object(self.timeout.time, "time", return_value=now):
            return self.action.run(self.ctx, self.argv)

    def assert_clean(self):
        self.assertNotIn(self.argv.node_name, self.timeout.timeout_mgr._monitoring_tasks)

    def set_match(self):
        box = [100, 200, 40, 40]
        detail = {"kyouma": {"02": {"res_1": {"box": box, "Level": "70", "ATK": "9000"}}}}
        result = NS(box=box, best_result=NS(detail=detail))
        self.argv.custom_action_param = json.dumps({"name": "kyouma", "id": 2})
        self.ctx.run_recognition.return_value = result
        return result

    def test_no_match_retries_after_timeout_window_in_both_modes(self):
        # Same action instance and real timer, as in the Android Agent process.
        for fast, now in [(True, 1000), (True, 1843.868), (False, 2046.395)]:
            with self.subTest(fast=fast, now=now):
                self.shared.select_support_fast = fast
                before = self.ctx.run_recognition.call_count
                self.assertFalse(self.run_at(now))
                self.assertGreater(self.ctx.run_recognition.call_count, before)
                self.assert_clean()
        self.module.logger.exception.assert_not_called()
        self.ctx.tasker.controller.post_click.assert_not_called()

    def test_success_after_previous_no_match(self):
        self.assertFalse(self.run_at(1000))
        self.set_match()
        self.assertTrue(self.run_at(1843.868))
        self.ctx.tasker.controller.post_click.assert_called_once()
        self.assert_clean()

    def test_normal_matching_still_clicks_in_both_modes(self):
        self.set_match()
        for fast in (True, False):
            with self.subTest(fast=fast):
                self.shared.select_support_fast = fast
                self.ctx.tasker.controller.post_click.reset_mock()
                self.assertTrue(self.run_at(1000))
                self.ctx.tasker.controller.post_click.assert_called_once()
                self.assert_clean()

    def test_json_support_configuration_still_works(self):
        self.set_match()
        self.argv.custom_action_param = json.dumps("default.json")
        self.module.data_io.find_target_files.return_value = {
            "team": {"SUPPORT": {"name": "kyouma", "id": 2}}}
        self.assertTrue(self.run_at(1000))
        self.ctx.tasker.controller.post_click.assert_called_once()
        self.assert_clean()

    def set_element_filter(self):
        self.argv.custom_action_param = json.dumps({"name": "kyouma", "id": 2})
        self.action.CHAR_DATA = {"kyouma": {"02": {"element": "fire"}}}
        self.action.UI_DATA = {"support": {"fire": "fight/support/support_fire.png"}}

    def test_element_fallback_no_match_is_clean(self):
        self.set_element_filter()
        for fast in (True, False):
            with self.subTest(fast=fast):
                self.shared.select_support_fast = fast
                self.assertFalse(self.run_at(1000))
                self.assert_clean()
        self.module.logger.exception.assert_not_called()
        self.ctx.tasker.controller.post_click.assert_not_called()

    def test_element_fallback_match_still_clicks(self):
        hit = self.set_match()
        self.set_element_filter()
        self.ctx.run_recognition.side_effect = [self.miss, self.miss, hit]
        self.module.match_mgr.group_info.side_effect = [
            (["first"], []), (["first"], []), (["filtered"], [[45, 190, 400, 150]])]
        self.assertTrue(self.run_at(1000))
        self.ctx.tasker.controller.post_click.assert_called_once()
        self.assert_clean()

    def test_recognition_exception_returns_failure_and_allows_retry(self):
        self.ctx.run_recognition.side_effect = RuntimeError("recognition failed")
        self.assertFalse(self.run_at(1000))
        self.assert_clean()
        self.module.logger.exception.assert_called_once()
        self.ctx.tasker.controller.post_click.assert_not_called()
        self.ctx.run_recognition.side_effect = None
        self.set_match()
        self.assertTrue(self.run_at(1843.868))
        self.assert_clean()

    def test_invalid_json_returns_failure_and_cleans_timer(self):
        self.argv.custom_action_param = "{invalid"
        self.assertFalse(self.run_at(1000))
        self.assert_clean()
        self.ctx.tasker.controller.post_click.assert_not_called()

    def test_expired_timer_is_cleared_on_failure(self):
        self.timeout.timeout_mgr._monitoring_tasks[self.argv.node_name] = 1000
        self.assertFalse(self.run_at(1843.868))
        self.assert_clean()
        self.ctx.run_recognition.assert_not_called()
        self.set_match()
        self.assertTrue(self.run_at(1850))
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
