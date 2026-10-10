"""Guard the tag -> APK build -> release upload path across workflow files."""
from pathlib import Path
import base64
import fnmatch
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

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
    def test_signing_secrets_reach_the_cloud_debug_build_and_verification_precedes_upload(self):
        names = {"ANDROID_KEYSTORE_BASE64", "ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD"}
        apk = load_workflow("android-apk.yml")
        self.assertEqual(set(apk["on"]["workflow_call"]["secrets"]), names)
        caller = load_workflow("install.yml")["jobs"]["android"]
        self.assertEqual(caller["secrets"], {name: "${{ secrets." + name + " }}" for name in names})
        steps = apk["jobs"]["build"]["steps"]
        build = next(step for step in steps if "build_mah.py" in step.get("run", ""))
        self.assertEqual(build["env"]["MAH_CI_DEBUG_SIGNING"], "true")
        self.assertEqual(build["env"]["KEYSTORE_PATH"], "${{ runner.temp }}/mah-signing.jks")
        for name in ("KEYSTORE_PASSWORD", "KEY_ALIAS", "KEY_PASSWORD"):
            self.assertEqual(build["env"][name], "${{ secrets.ANDROID_" + name + " }}")
        verify = next(i for i, step in enumerate(steps) if step["name"] == "Verify APK signing certificate")
        upload = next(i for i, step in enumerate(steps) if step.get("uses", "").startswith("actions/upload-artifact@"))
        self.assertLess(steps.index(build), verify)
        self.assertLess(verify, upload)

    def test_cloud_key_restore_cleanup_and_missing_secret_failure(self):
        steps = load_workflow("android-apk.yml")["jobs"]["build"]["steps"]
        restore = next(step for step in steps if step["name"] == "Restore APK signing key")
        cleanup = next(step for step in steps if step["name"] == "Remove APK signing key")
        self.assertEqual(cleanup["if"], "always()")
        with tempfile.TemporaryDirectory() as directory:
            env = {"RUNNER_TEMP": directory, "KEYSTORE_BASE64": base64.b64encode(b"test-keystore").decode(),
                   "KEYSTORE_PASSWORD": "test-password", "KEY_ALIAS": "test", "KEY_PASSWORD": "test-password"}
            with patch.dict(os.environ, env):
                exec(restore["run"], {})
                key = Path(directory) / "mah-signing.jks"
                self.assertEqual(key.read_bytes(), b"test-keystore")
                exec(cleanup["run"], {})
                self.assertFalse(key.exists())
                with patch.dict(os.environ, {"KEY_PASSWORD": ""}):
                    with self.assertRaisesRegex(SystemExit, "ANDROID_KEY_PASSWORD"):
                        exec(restore["run"], {})
                self.assertFalse(key.exists())

    def test_certificate_verification_rejects_a_different_apk_key(self):
        steps = load_workflow("android-apk.yml")["jobs"]["build"]["steps"]
        script = next(step["run"] for step in steps if step["name"] == "Verify APK signing certificate")
        certificate = b"configured-certificate"
        expected = hashlib.sha256(certificate).hexdigest()
        env = {"KEYSTORE_PATH": "test.jks", "KEY_ALIAS": "test", "ANDROID_HOME": "sdk"}
        for matches in (True, False):
            digest = expected if matches else "0" * 64
            with patch.dict(os.environ, env), patch("subprocess.check_output", side_effect=[
                certificate, f"Signer #1 certificate SHA-256 digest: {digest}\n",
            ]), patch("builtins.print"):
                if matches:
                    exec(script, {})
                else:
                    with self.assertRaisesRegex(SystemExit, "does not match"):
                        exec(script, {})

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

    def test_desktop_archives_are_windows_only(self):
        matrix = load_workflow("install.yml")["jobs"]["install"]["strategy"]["matrix"]
        self.assertNotIn("android", matrix["os"])
        self.assertEqual(set(matrix["os"]), {"win"})

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
