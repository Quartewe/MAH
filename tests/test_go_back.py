"""Replay loading -> dungeon list -> home at the real GoBack action boundary."""

from contextlib import redirect_stdout
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from agent_modules import load_agent_module


class ReturnScreen:
    def __init__(self, loading_frames=2, stuck_back=False):
        self.loading_frames = loading_frames
        self.stuck_back = stuck_back
        self.screen = "loading" if loading_frames else "dungeon-list"
        self.back_checked_on = []
        self.clicked = 0
        self.controller = SimpleNamespace(post_screencap=self.capture, cached_image=None)
        self.tasker = SimpleNamespace(controller=self.controller, stopping=False)

    def capture(self):
        self.controller.cached_image = self.screen
        if self.screen == "loading":
            self.loading_frames -= 1
            if self.loading_frames == 0:
                self.screen = "dungeon-list"
        return Mock()

    def run_recognition(self, entry, image, pipeline_override):
        expected = pipeline_override[entry]["recognition"]["param"]["expected"]
        if expected == "LOADING":
            hit = image == "loading"
        else:
            self.back_checked_on.append(image)
            hit = image == "dungeon-list"
        return SimpleNamespace(best_result=SimpleNamespace(box=[32, 45, 64, 36]) if hit else None)

    def run_action(self, *args, **kwargs):
        self.clicked += 1
        if not self.stuck_back:
            self.screen = "home"
        return SimpleNamespace(success=True)


class GoBackTests(unittest.TestCase):
    def setUp(self):
        self.module = load_agent_module("agent/custom/action/go_back.py")
        self.argv = SimpleNamespace(node_name="Global.GoBackToHomePage", custom_action_param='"返回"')

    def run_action(self, screen):
        with patch.object(self.module.time, "sleep"), redirect_stdout(io.StringIO()):
            return self.module.GoBack().run(screen, self.argv)

    def test_rechecks_back_after_loading_disappears(self):
        screen = ReturnScreen()
        self.assertTrue(self.run_action(screen))
        self.assertIn("dungeon-list", screen.back_checked_on)
        self.assertEqual(screen.clicked, 1)
        self.assertEqual(screen.screen, "home")

    def test_direct_return_still_works(self):
        screen = ReturnScreen(loading_frames=0)
        self.assertTrue(self.run_action(screen))
        self.assertEqual(screen.clicked, 1)

    def test_loading_checks_timeout_and_cleans_up(self):
        screen = ReturnScreen(loading_frames=20)
        self.module.timeout_mgr.check_timeout.side_effect = [False, False, True]
        self.assertFalse(self.run_action(screen))
        self.assertEqual(screen.clicked, 0)
        self.module.timeout_mgr.stop_monitoring.assert_called_once_with(self.argv.node_name)

    def test_cancelled_task_does_not_click(self):
        screen = ReturnScreen(loading_frames=0)
        screen.tasker.stopping = True
        self.assertFalse(self.run_action(screen))
        self.assertEqual(screen.clicked, 0)

    def test_stuck_back_button_is_bounded(self):
        screen = ReturnScreen(loading_frames=0, stuck_back=True)
        self.assertFalse(self.run_action(screen))
        self.assertEqual(screen.clicked, 15)


if __name__ == "__main__":
    unittest.main()
