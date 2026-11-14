"""Exercise the release-note composer embedded in the publishing workflow."""

from contextlib import chdir
from io import StringIO
from pathlib import Path
import json
import os
import re
import tempfile
import unittest
from unittest.mock import patch

import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/install.yml"
UI_BODY = "### Feat\n\n- 新增 UI 功能\n\n### Fix\n\n- 修复 UI 问题\n"
BASE_BODY = "## 2.0.6\n\n### 新功能\n\n- 主项目功能\n\n### Bug修复\n\n- 主项目修复\n"
VERSION_MARKER = "<!-- mah-ui-version: v1.4.4 -->"


def release(tag, body, **fields):
    return {
        "tag_name": tag,
        "body": body,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-11-01T00:00:00Z",
        **fields,
    }


class ReleaseNotesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        step = next(
            step for step in workflow["jobs"]["changelog"]["steps"]
            if step.get("id") == "compose_release_body"
        )
        cls.script = step["run"].split("python - <<'PY'\n", 1)[1].split("\nPY", 1)[0]

    def compose(self, *, base=BASE_BODY, ui_body=UI_BODY, ui_version="v1.4.4",
                history=(), target_tag="v2.0.6", prerelease=False, resource="资源#261028"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGES.md").write_text(base, encoding="utf-8")
            (root / "ui.md").write_text(ui_body, encoding="utf-8")
            # Also feed the old composer so these tests expose its original failures.
            previous = next((item["body"] for item in history if not item["draft"]), "")
            (root / "previous.md").write_text(previous, encoding="utf-8")
            output = root / "output.txt"
            env = {
                "UI_BODY_FILE": str(root / "ui.md"),
                "PREVIOUS_BODY_FILE": str(root / "previous.md"),
                "GITHUB_OUTPUT": str(output),
                "GITHUB_REPOSITORY": "Quartewe/MAH",
                "GITHUB_TOKEN": "test-token",
                "RESOURCE_VERSION": resource,
                "UI_VERSION": ui_version,
                "TARGET_TAG": target_tag,
                "IS_PRERELEASE": str(prerelease).lower(),
            }
            pages = [list(history[offset:offset + 100]) for offset in range(0, len(history), 100)]
            if not pages or len(pages[-1]) == 100:
                pages.append([])
            responses = [StringIO(json.dumps(page)) for page in pages]
            with patch.dict(os.environ, env), chdir(root), patch(
                "urllib.request.urlopen", side_effect=responses
            ) as request:
                exec(compile(self.script, str(WORKFLOW), "exec"), {})
            value = output.read_text(encoding="utf-8")
            self.assertTrue(value.startswith("release_body<<EOF\n"))
            self.assertTrue(value.endswith("\nEOF\n"))
            return value[len("release_body<<EOF\n"):-len("EOF\n")], request.call_args_list

    def assert_ui_section(self, body, count):
        self.assertEqual(len(re.findall(r"^#{1,6}\s+UI更新[:：]?\s*$", body, re.M)), count)

    def test_features_and_fixes_share_one_independent_ui_section(self):
        body, _ = self.compose()
        self.assert_ui_section(body, 1)
        self.assertIn("### UI更新\n\n#### 新功能", body)
        self.assertIn("#### Bug修复\n\n- 修复 UI 问题", body)
        self.assertIn("- 新增 UI 功能", body)
        self.assertIn("- 主项目功能", body)
        self.assertIn("- 主项目修复", body)
        self.assertIn("- 资源更新到: 资源#261028", body)
        self.assertEqual(body.count(VERSION_MARKER), 1)

    def test_ui_content_does_not_require_matching_mah_categories(self):
        for base in ("### Bug修复\n- 主项目修复\n", "### 日常维护\n- 调整配置\n", ""):
            with self.subTest(base=base):
                body, _ = self.compose(base=base)
                self.assert_ui_section(body, 1)
                self.assertIn("- 新增 UI 功能", body)
                self.assertIn("- 修复 UI 问题", body)

    def test_same_ui_version_stays_suppressed_across_releases(self):
        history = [release("v2.0.3", VERSION_MARKER)]
        for tag in ("v2.0.4", "v2.0.5", "v2.0.6"):
            with self.subTest(tag=tag):
                body, _ = self.compose(history=history, target_tag=tag)
                self.assert_ui_section(body, 0)
                self.assertIn(VERSION_MARKER, body)
                history.insert(0, release(tag, body))

    def test_new_ui_version_is_included_even_if_text_matches_an_older_version(self):
        older = UI_BODY + "\n<!-- mah-ui-version: v1.4.3 -->\n"
        body, _ = self.compose(history=[release("v2.0.5", older)])
        self.assert_ui_section(body, 1)
        self.assertIn("- 新增 UI 功能", body)
        self.assertIn(VERSION_MARKER, body)

    def test_legacy_notes_are_found_before_an_intervening_release_without_ui(self):
        legacy = "### 新功能\n\n#### UI更新:\n\n- 新增 UI 功能\n"
        legacy += "\n### Bug修复\n\n#### UI更新:\n\n- 修复 UI 问题\n"
        body, _ = self.compose(history=[
            release("v2.0.4", "### 新功能\n- 主项目功能\n"),
            release("v2.0.3", legacy),
        ])
        self.assert_ui_section(body, 0)
        self.assertIn(VERSION_MARKER, body)

    def test_legacy_partial_notes_only_suppress_the_published_ui_group(self):
        legacy = "### 新功能\n\n#### UI更新:\n\n- 新增 UI 功能\n"
        body, _ = self.compose(history=[release("v2.0.3", legacy)])
        self.assert_ui_section(body, 1)
        self.assertNotIn("- 新增 UI 功能", body)
        self.assertIn("- 修复 UI 问题", body)

    def test_ordinary_mah_notes_do_not_count_as_published_ui_notes(self):
        body, _ = self.compose(history=[release("v2.0.5", UI_BODY)])
        self.assert_ui_section(body, 1)
        self.assertIn("- 新增 UI 功能", body)
        self.assertIn("- 修复 UI 问题", body)

    def test_history_pagination_reaches_older_version_markers(self):
        history = [release(f"v3.0.{index}", "### 日常维护\n") for index in range(100)]
        history.append(release("v2.0.3", VERSION_MARKER))
        body, requests = self.compose(history=history)
        self.assert_ui_section(body, 0)
        self.assertEqual(len(requests), 2)
        self.assertTrue(requests[0].args[0].full_url.endswith("per_page=100&page=1"))
        self.assertTrue(requests[1].args[0].full_url.endswith("per_page=100&page=2"))

    def test_drafts_and_prereleases_do_not_suppress_stable_release_notes(self):
        body, _ = self.compose(history=[
            release("v2.0.6-alpha1", VERSION_MARKER, prerelease=True),
            release("v2.0.6-draft", VERSION_MARKER, draft=True),
        ])
        self.assert_ui_section(body, 1)

    def test_prerelease_can_reuse_ui_version_from_an_earlier_prerelease(self):
        body, _ = self.compose(
            target_tag="v2.0.6-alpha2", prerelease=True,
            history=[release("v2.0.6-alpha1", VERSION_MARKER, prerelease=True)],
        )
        self.assert_ui_section(body, 0)
        self.assertIn(VERSION_MARKER, body)

    def test_rerunning_a_release_ignores_itself_and_later_releases(self):
        expected, _ = self.compose()
        body, _ = self.compose(history=[
            release("v2.0.7", VERSION_MARKER, published_at="2026-11-07T00:00:00Z"),
            release("v2.0.6", expected, published_at="2026-11-06T00:00:00Z"),
            release("v2.0.5", "旧公告", published_at="2026-11-05T00:00:00Z"),
        ])
        self.assertEqual(body, expected)

    def test_empty_ui_notes_do_not_record_a_version_or_fetch_history(self):
        for ui_body in ("", "### Chore\n- 调整配置\n"):
            with self.subTest(ui_body=ui_body):
                body, requests = self.compose(ui_body=ui_body)
                self.assert_ui_section(body, 0)
                self.assertNotIn(VERSION_MARKER, body)
                self.assertEqual(requests, [])
                self.assertIn("- 主项目功能", body)


if __name__ == "__main__":
    unittest.main()
