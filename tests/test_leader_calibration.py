"""Opening skills move the visible L marker before the board is ready."""

from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from agent_modules import load_agent_module


class OpeningScreen:
    def __init__(self, wait_seconds=2, wait_success=True, cancel_during_wait=False):
        self.now = 0
        self.wait_seconds = wait_seconds
        self.wait_success = wait_success
        self.cancel_during_wait = cancel_during_wait
        self.screen = "opening"
        self.events = []
        self.tasker = NS(stopping=False, controller=NS(
            cached_image="opening", post_screencap=self.capture))

    def capture(self):
        self.events.append("capture")
        self.tasker.controller.cached_image = self.screen
        return Mock()

    def run_action(self, entry, pipeline_override):
        node = pipeline_override[entry]
        if node.get("action", {}).get("type") != "DoNothing":
            raise AssertionError("Calibration must not move a unit")
        self.events.append("wait")
        # Like native Maa, a freeze timeout can still report action success.
        if node.get("pre_wait_freezes"):
            self.now += self.wait_seconds
            self.screen = "ready"
        if self.cancel_during_wait:
            self.tasker.stopping = True
        return NS(success=self.wait_success)

    def run_recognition(self, entry, image, pipeline_override):
        self.events.append("recognize")
        # Recognition only reads the supplied image; pipeline waits do not run.
        # Both marker coordinates were captured without any player movement.
        box = [775, 422, 23, 23] if image == "opening" else [887, 422, 23, 23]
        result = NS(box=box, score=0.94)
        return NS(best_result=result, all_results=[result])


class LeaderCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.module = load_agent_module("agent/custom/action/auto_combat.py",
            proj_path=NS(AUTO_COMBAT_DIR="unused"), act_mgr=Mock())
        self.action = self.module.AutoCombat()

    def calibrate(self, screen):
        with patch.object(self.module.time, "monotonic", side_effect=lambda: screen.now), \
             patch.object(self.module.time, "sleep"):
            return self.action._get_posL(screen)

    def test_opening_knockback_uses_fresh_settled_frame(self):
        screen = OpeningScreen()
        self.assertEqual(self.calibrate(screen), [925, 417])
        self.assertEqual(screen.events, ["wait", "capture", "recognize"])

    def test_freeze_timeout_is_not_successful_calibration(self):
        screen = OpeningScreen(wait_seconds=15, wait_success=True)
        self.assertIsNone(self.calibrate(screen))
        self.assertNotIn("recognize", screen.events)

    def test_failed_wait_stops_before_recognition(self):
        screen = OpeningScreen(wait_success=False)
        self.assertIsNone(self.calibrate(screen))
        self.assertNotIn("recognize", screen.events)

    def test_cancellation_during_wait_does_not_accept_a_position(self):
        screen = OpeningScreen(cancel_during_wait=True)
        self.assertIsNone(self.calibrate(screen))
        self.assertNotIn("recognize", screen.events)

    def test_cancelled_task_does_not_start_waiting(self):
        screen = OpeningScreen()
        screen.tasker.stopping = True
        self.assertIsNone(self.calibrate(screen))
        self.assertEqual(screen.events, [])


if __name__ == "__main__":
    unittest.main()
