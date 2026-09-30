"""Guard the tag -> APK build -> release upload path across workflow files."""
from pathlib import Path
import fnmatch
import unittest

import yaml


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def load_workflow(name):
    return yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def dependency_steps(workflow, job_name):
    job = workflow["jobs"][job_name]
    dependencies = job.get("needs", [])
    if isinstance(dependencies, str):
        dependencies = [dependencies]
    for dependency in dependencies:
        yield from dependency_steps(workflow, dependency)
    if job.get("uses", "").startswith("./.github/workflows/"):
        called = load_workflow(Path(job["uses"]).name)
        for called_job in called["jobs"]:
            yield from dependency_steps(called, called_job)
    yield from job.get("steps", [])


class AndroidReleaseWorkflowTests(unittest.TestCase):
    def test_tag_release_waits_for_apk_and_project_package(self):
        install = load_workflow("install.yml")
        steps = list(dependency_steps(install, "release"))
        produced = {
            step.get("with", {}).get("name")
            for step in steps
            if step.get("uses", "").startswith("actions/upload-artifact@")
        }
        self.assertTrue(
            {"MAH-Android-APK", "MAH-Android-project"}.issubset(produced),
            f"Release dependencies do not produce the Android deliverables: {produced}",
        )
        self.assertTrue(any("build_mah.py" in step.get("run", "") for step in steps))

    def test_release_downloads_and_publishes_actual_android_files(self):
        release = load_workflow("install.yml")["jobs"]["release"]
        downloads = {
            step.get("with", {}).get("name"): step.get("with", {}).get("path")
            for step in release["steps"]
            if step.get("uses", "").startswith("actions/download-artifact@")
        }
        publisher = next(
            step for step in release["steps"]
            if step.get("uses", "").startswith("softprops/action-gh-release@")
        )
        patterns = publisher["with"]["files"].splitlines()
        for artifact, filename in (
            ("MAH-Android-APK", "MAH-android-universal-v2.0.0-beta1-debug.apk"),
            ("MAH-Android-project", "MAH-project-android-v2.0.0-beta1.zip"),
        ):
            self.assertIn(artifact, downloads)
            path = f"{downloads[artifact]}/{filename}"
            self.assertTrue(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns), path)
            # Android files must not enter the desktop ZIP/incremental repacking loop.
            self.assertNotEqual(downloads[artifact], "assets")

    def test_android_is_not_built_as_a_desktop_archive(self):
        matrix = load_workflow("install.yml")["jobs"]["install"]["strategy"]["matrix"]
        self.assertNotIn("android", matrix["os"])
        self.assertEqual(set(matrix["os"]), {"win", "macos", "linux"})

    def test_project_package_does_not_publish_a_separate_tag_release(self):
        project = load_workflow("android-project.yml")
        self.assertNotIn("push", project["on"])
        for job in project["jobs"].values():
            for step in job.get("steps", []):
                self.assertNotIn("gh release", step.get("run", ""))

    def test_main_push_and_tag_release_share_the_apk_builder(self):
        apk = load_workflow("android-apk.yml")
        self.assertIn("main", apk["on"]["push"]["branches"])
        self.assertIn("workflow_call", apk["on"])
        install = load_workflow("install.yml")
        caller = next(
            (job for job in install["jobs"].values()
             if job.get("uses") == "./.github/workflows/android-apk.yml"),
            None,
        )
        self.assertIsNotNone(caller)
        self.assertEqual(caller["with"]["version"], "${{ needs.meta.outputs.tag }}")


if __name__ == "__main__":
    unittest.main()
