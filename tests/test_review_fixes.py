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












if __name__ == "__main__":
    unittest.main()
