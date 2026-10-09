"""Exercise the actual staging output, including overlapping resource ownership."""
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location(
    "build_android", Path(__file__).resolve().parents[1] / "tools/build_android.py"
)
build_android = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_android)


class AndroidLightBundleTests(unittest.TestCase):
    def test_light_bundle_retains_project_assets_and_excludes_external_images_and_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mah"
            resources = Path(directory) / "mah_res"

            def write(base, name, text):
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            for name, text in {
                "assets/interface.json": '{"interface_version":2,"resource_github":"https://github.com/owner/resources"}',
                "assets/icon.png": "icon", "LICENSE": "license",
                "config/maa_option.json": "{}", "agent/main.py": "# agent",
                "data/default.json": "{}", "data/state.json": "user state",
                "assets/resource/base/image/own.png": "own UI",
                "assets/resource/base/image/character/a.png": "overlapping image",
                "assets/resource/index/ui.json": "overlapping index",
                **{f"assets/resource/base/model/ocr/{name}": "model" for name in ("rec.onnx", "det.onnx", "keys.txt")},
                **{f"docs/{lang}/welcome.md": "welcome" for lang in ("zh_cn", "en_us", "ja_jp", "zh_tw")},
            }.items():
                write(root, name, text)
            for name, text in {
                "image/character/a.png": "character", "image/ar/b.png": "ar",
                **{f"index/{name}.json": "{}" for name in ("ui", "characters", "ar")},
            }.items():
                write(resources, name, text)
            output = root / "build/android/pi"
            with patch.object(build_android, "ROOT", root):
                archive = build_android.stage(output, resources, "v-test", "res-test")
            self.assertFalse((output / "resource/base/image/character/a.png").exists())
            self.assertFalse((output / "resource/index/ui.json").exists())
            self.assertFalse((output / "data/state.json").exists())
            self.assertTrue((output / "resource/base/image/own.png").is_file())
            self.assertTrue((output / "resource/base/model/ocr/rec.onnx").is_file())
            state = json.loads((output / ".mah-install.json").read_text())
            self.assertEqual(state["resourceVersion"], "")
            self.assertEqual(state["owners"]["resource"], {})
            self.assertEqual(json.loads((output / "interface.json").read_text())["resource_version"], "")
            with zipfile.ZipFile(archive) as package:
                names = set(package.namelist())
                self.assertIn("agent/main.py", names)
                self.assertNotIn("data/state.json", names)
                self.assertNotIn("resource/base/image/character/a.png", names)
                manifest = json.loads(package.read("mah-package.json"))
                self.assertEqual(set(manifest["files"]), names - {"mah-package.json"})


if __name__ == "__main__":
    unittest.main()
