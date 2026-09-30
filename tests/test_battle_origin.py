"""Keep the opening board origin after the leader disappears, until results."""

from contextlib import redirect_stderr, redirect_stdout
import io
import itertools
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from agent_modules import load_agent_module


def recognition(text=None, box=None):
    hits = [] if text is None else [NS(text=text, box=box or [1100, 550, 80, 30])]
    return NS(best_result=hits[0] if hits else None, all_results=hits, filtered_results=hits)


class BattleScreen:
    def __init__(self, origin=(700, 500), required_moves=1, results_after=4,
                 cancel_after=None, error_after=None):
        self.origin = origin
        self.required_moves = required_moves
        self.results_after = results_after
        self.cancel_after = cancel_after
        self.error_after = error_after
        self.moves = []
        self.leader_lookups = 0
        self.completion_checks = 0
        self.saw_results = False
        self.tasker = NS(stopping=False, controller=NS(
            post_screencap=Mock(return_value=Mock()), cached_image=None))

    def run_recognition(self, entry, image, pipeline_override):
        params = pipeline_override[entry]["recognition"]["param"]
        if params.get("template") == "fight/L.png":
            self.leader_lookups += 1
            if self.origin is None or self.moves:
                return recognition()
            return recognition("L", [self.origin[0] - 38, self.origin[1] + 5, 23, 23])
        expected = params.get("expected")
        if isinstance(expected, list) and "TOUCHSCREEN" in expected:
            self.completion_checks += 1
            if self.cancel_after and self.completion_checks >= self.cancel_after:
                self.tasker.stopping = True
            if self.error_after and self.completion_checks >= self.error_after:
                return None
        if isinstance(expected, list) and "再次挑战" in expected:
            if self.results_after is not None and self.completion_checks >= self.results_after and len(self.moves) >= self.required_moves:
                self.saw_results = True
                return recognition("再次挑战")
        return recognition()

    def run_action(self, entry, pipeline_override, **kwargs):
        if entry != "UtilsSwipe":
            raise AssertionError(f"Unexpected action: {entry}")
        self.moves.append(pipeline_override[entry]["begin"][:2])
        return NS(success=True)


class BattleOriginTests(unittest.TestCase):
    def setUp(self):
        self.shared = NS(combat_set=True, auto_combat_mode=False, leader_pos=[], current_lang="cn")
        self.module = load_agent_module(
            "agent/custom/action/auto_combat.py", info_share=self.shared,
            proj_path=NS(AUTO_COMBAT_DIR="unused"), act_mgr=Mock())
        self.action = self.module.AutoCombat()
        self.argv = NS(node_name="Global.AutoCombat", custom_action_param="script")
        self.script = {"fight": {"pos": {"1": [0, 0], "2": [1, 0]},
                                  "action": {"0": {"char": 2, "action": ["R"]}}}}
        self.module.data_io.find_target_files.return_value = self.script

    def run_battle(self, screen):
        with patch.object(self.module.time, "sleep"), \
             patch.object(self.module.time, "monotonic", side_effect=itertools.count(0, 100)), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.action.run(screen, self.argv)

    def test_script_end_waits_for_results_without_finding_dead_leader_again(self):
        screen = BattleScreen()
        self.assertTrue(self.run_battle(screen))
        self.assertTrue(screen.saw_results, "Finishing the script is not battle completion")
        self.assertEqual(screen.moves, [[810, 500]])
        self.assertEqual(screen.leader_lookups, 1)
        self.assertEqual(self.shared.leader_pos, [])

    def test_loop_keeps_origin_and_relative_positions_after_leader_disappears(self):
        self.script["fight"]["action"]["loop"] = {"0": {"char": 2, "action": ["L"]}}
        screen = BattleScreen(required_moves=3, results_after=1)
        self.assertTrue(self.run_battle(screen))
        self.assertTrue(screen.saw_results)
        self.assertEqual(screen.moves, [[810, 500], [920, 500], [810, 500]])
        self.assertEqual(screen.leader_lookups, 1)
        self.assertEqual(self.shared.leader_pos, [])

    def test_next_battle_uses_its_own_origin_without_cross_battle_recheck(self):
        first = BattleScreen(results_after=2)
        second = BattleScreen(origin=(920, 500), results_after=2)
        self.assertTrue(self.run_battle(first))
        self.assertTrue(self.run_battle(second))
        self.assertEqual(first.leader_lookups, 1)
        self.assertEqual(second.leader_lookups, 1)
        self.assertEqual(second.moves, [[1030, 500]])
        self.assertEqual(self.shared.leader_pos, [])

    def test_unfinished_battle_times_out_instead_of_reporting_success(self):
        screen = BattleScreen(results_after=None)
        self.assertFalse(self.run_battle(screen))
        self.assertEqual(len(screen.moves), 1)
        self.assertLess(screen.completion_checks, 10)
        self.assertEqual(self.shared.leader_pos, [])

    def test_cancel_while_waiting_does_not_report_completion(self):
        screen = BattleScreen(results_after=None, cancel_after=3)
        self.assertFalse(self.run_battle(screen))
        self.assertTrue(screen.tasker.stopping)
        self.assertEqual(self.shared.leader_pos, [])

    def test_recognition_failure_while_waiting_does_not_report_completion(self):
        screen = BattleScreen(results_after=None, error_after=3)
        self.assertFalse(self.run_battle(screen))
        self.assertFalse(screen.saw_results)
        self.assertEqual(self.shared.leader_pos, [])

    def test_failed_battle_does_not_leak_origin_into_next_battle(self):
        failed = BattleScreen(results_after=None)
        self.assertFalse(self.run_battle(failed))
        self.assertEqual(self.shared.leader_pos, [])
        next_battle = BattleScreen(origin=(920, 500), results_after=2)
        self.assertTrue(self.run_battle(next_battle))
        self.assertEqual(next_battle.leader_lookups, 1)
        self.assertEqual(next_battle.moves, [[1030, 500]])

    def test_missing_opening_leader_cannot_use_previous_battle_origin(self):
        self.shared.leader_pos = [700, 500]
        screen = BattleScreen(origin=None)
        self.assertFalse(self.run_battle(screen))
        self.assertEqual(screen.moves, [])
        self.assertEqual(self.shared.leader_pos, [])


if __name__ == "__main__":
    unittest.main()
