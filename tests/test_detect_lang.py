"""Use the actual language classifier with OCR text captured from the potion panel."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from agent_modules import load_agent_module


class DetectLangTests(unittest.TestCase):
    def setUp(self):
        self.module = load_agent_module("agent/utils/action_helpers.py")

    def detect(self, texts, previous="cn"):
        self.module.info_share.current_lang = previous
        results = [SimpleNamespace(text=text) for text in texts]
        context = Mock()
        context.run_recognition.return_value = SimpleNamespace(best_result=results[0], filtered_results=results)
        return self.module.ActUtils.detect_lang(context, [0, 0, 100, 100])

    def test_quantity_only_ocr_preserves_known_language(self):
        for language in ("cn", "tw", "jp", "en"):
            with self.subTest(language=language):
                self.assertEqual(self.detect(["×3", "×3", "X1", "X1", "X1", "×20", "X1"], language), language)
                self.assertEqual(self.module.info_share.current_lang, language)

    def test_quantity_formats_are_not_english_evidence(self):
        for text in ["x 20", "20 X", "Ｘ１０", "1,000", "123", "× 3"]:
            with self.subTest(text=text):
                self.assertEqual(self.detect([text]), "cn")

    def test_no_evidence_does_not_invent_a_language(self):
        self.assertEqual(self.detect(["×3", "X1", "..."], previous=""), "")
        self.assertEqual(self.module.info_share.current_lang, "")

    def test_meaningful_language_can_replace_previous_value(self):
        for text, expected in (("Back", "en"), ("戻る", "jp"), ("体力恢复", "cn"), ("體力恢復", "tw")):
            with self.subTest(text=text):
                self.assertEqual(self.detect([text, "X1"], previous="jp"), expected)

    def test_chinese_wins_over_fixed_english_labels(self):
        self.assertEqual(self.detect(["体力恢复", "LEADER", "SUPPORT", "Level"]), "cn")

    def test_empty_compare_list_does_not_capture_screen(self):
        self.module.info_share.current_lang = "tw"
        context = Mock()
        result = self.module.ActUtils.detect_lang(context, [0, 0, 100, 100], compare_list=[])
        self.assertEqual(result, "")
        self.assertEqual(self.module.info_share.current_lang, "tw")
        context.run_recognition.assert_not_called()

    def test_ocr_path_uses_same_quantity_filter(self):
        self.module.info_share.current_lang = "cn"
        results = [SimpleNamespace(text=t) for t in ["X1", "×3"]]
        context = Mock()
        context.run_recognition.return_value = SimpleNamespace(best_result=results[0], filtered_results=results)
        self.assertEqual(self.module.ActUtils.detect_lang(context, [286, 298, 779, 295]), "cn")


if __name__ == "__main__":
    unittest.main()
