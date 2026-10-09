"""Stage MAH for MaaFwApp and produce an independently installable project archive.

Images and indexes are downloaded on first use from resource_github. Project
updates leave those files to that channel and never ship user state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDES = {"__pycache__", ".git", ".DS_Store"}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def files(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file()
                  and not any(part in EXCLUDES for part in p.parts)
                  and p.suffix not in {".pyc", ".pyo"})


def copy_tree(source: Path, dest: Path):
    for path in files(source):
        out = dest / path.relative_to(source)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)


def git_version(repo: Path) -> str:
    result = subprocess.run(["git", "-C", str(repo), "describe", "--tags", "--always"],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    return result.stdout.strip()


def stage(output: Path, resources: Path, version: str, resource_version: str) -> Path:
    output = output.resolve()
    # This is a generated subtree only. Refuse a typo targeting a checkout.
    build_root = (ROOT / "build" / "android").resolve()
    if output == build_root or not output.is_relative_to(build_root):
        raise ValueError("Output must be a child of MAH/build/android")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    copy_tree(ROOT / "assets" / "resource", output / "resource")
    for directory in ("agent", "data"):
        copy_tree(ROOT / directory, output / directory)
    for language in ("zh_cn", "en_us", "ja_jp", "zh_tw"):
        source = ROOT / "docs" / language / "welcome.md"
        dest = output / "docs" / language / "welcome.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    # State is runtime data, not a default that should travel to other users.
    (output / "data" / "state.json").unlink(missing_ok=True)
    (output / "config").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "config" / "maa_option.json", output / "config" / "maa_option.json")
    for filename in ("icon.png", "interface.json"):
        shutil.copy2(ROOT / "assets" / filename, output / filename)
    shutil.copy2(ROOT / "LICENSE", output / "LICENSE")

    ocr = output / "resource" / "base" / "model" / "ocr"
    if not (ocr / "rec.onnx").is_file():
        copy_tree(ROOT / "assets" / "MaaCommonAssets" / "OCR" / "ppocr_v5" / "zh_cn", ocr)
    for required in ("rec.onnx", "det.onnx", "keys.txt"):
        if not (ocr / required).is_file():
            raise ValueError(f"Missing OCR model: {ocr / required}")

    resource_files = {}
    for source, destination in (("image", "resource/base/image"), ("index", "resource/index"),
                                ("model", "resource/base/model"), ("pipeline", "resource/base/pipeline")):
        for path in files(resources / source):
            name = f"{destination}/{path.relative_to(resources / source).as_posix()}"
            out = output / name
            out.parent.mkdir(parents=True, exist_ok=True)
            resource_files[name] = digest(path)
            if source in {"image", "index"}:
                # Even an overlapping file from assets/resource must stay external.
                out.unlink(missing_ok=True)
            else:
                shutil.copy2(path, out)
    for name in ("ui.json", "characters.json", "ar.json"):
        json.loads((resources / "index" / name).read_text(encoding="utf-8"))
    for name in ("character", "ar"):
        if not any((resources / "image" / name).glob("*")):
            raise ValueError(f"Missing external {name} images")

    interface_path = output / "interface.json"
    interface = json.loads(interface_path.read_text(encoding="utf-8"))
    interface.update(version=version, resource_version="")
    interface["software_github"] = "https://github.com/Quartewe/MAH"
    # The desktop RID has no Android APK distribution configured.
    interface.pop("mirrorchyan_rid", None)
    interface["project_github"] = "https://github.com/Quartewe/MAH"
    agents = interface.get("agent", [])
    for agent in ([agents] if isinstance(agents, dict) else agents):
        agent["child_args"] = ["./agent/main.py" if arg == "../agent/main.py" else arg
                               for arg in agent.get("child_args", [])]
    interface_path.write_text(json.dumps(interface, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    project_files = {p.relative_to(output).as_posix(): digest(p) for p in files(output)
                     if p.relative_to(output).as_posix() not in resource_files}
    manifest = {"format": 1, "target": "project", "version": version,
                "framework": "v5.14.2", "agentCore": "3.13.15-maafw5.14.2",
                "files": project_files}
    (output / "mah-package.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    state = {"projectVersion": version, "resourceVersion": "",
             "revision": f"bundle-{version}-{resource_version}",
             "owners": {"project": project_files, "resource": {}}}
    (output / ".mah-install.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    archive = output.parent / f"MAH-project-android-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name in [*project_files, "mah-package.json"]:
            zip_file.write(output / name, name)
    print(f"PI: {output}\nProject update: {archive}\nSHA-256: {digest(archive)}")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources", type=Path, default=ROOT.parent / "mah_res")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "android" / "pi")
    parser.add_argument("--version", default=None)
    parser.add_argument("--resource-version", default=None)
    args = parser.parse_args()
    stage(args.output, args.resources.resolve(), args.version or git_version(ROOT),
          args.resource_version or git_version(args.resources))
