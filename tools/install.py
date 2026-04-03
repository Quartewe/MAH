from pathlib import Path
import re
import tempfile
import subprocess

import shutil
import sys
import urllib.request
import zipfile

try:
    import jsonc
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments\n"
        "Or add it to your project's requirements."
    ) from e

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.resolve()
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"
resource_version_override = len(sys.argv) > 4 and sys.argv[4] or ""

# the first parameter is self name
if sys.argv.__len__() < 4:
    print("[DEBUG] Usage: python install.py <version> <os> <arch> [resource_version]")
    print("[DEBUG] Example: python install.py v1.0.0 win x86_64 v1.0.1")
    sys.exit(1)

os_name = sys.argv[2]
arch = sys.argv[3]


def resolve_windows_python_runtime_dir() -> Path:
    """根据包体结构解析 Windows 内置 Python 目录，优先选择包含 pythonXYZ.dll 的目录。"""
    candidates = [install_path / "_internal", install_path / "python"]

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_dir():
            continue
        for dll in candidate.glob("python*.dll"):
            if re.fullmatch(r"python(\d{3})\.dll", dll.name.lower()):
                return candidate

    for candidate in candidates:
        if (candidate / "python.exe").exists():
            return candidate

    # 兜底保持当前项目结构
    return install_path / "_internal"


def get_dotnet_platform_tag():
    """自动检测当前平台并返回对应的dotnet平台标签"""
    if os_name == "win" and arch == "x86_64":
        platform_tag = "win-x64"
    elif os_name == "win" and arch == "aarch64":
        platform_tag = "win-arm64"
    elif os_name == "macos" and arch == "x86_64":
        platform_tag = "osx-x64"
    elif os_name == "macos" and arch == "aarch64":
        platform_tag = "osx-arm64"
    elif os_name == "linux" and arch == "x86_64":
        platform_tag = "linux-x64"
    elif os_name == "linux" and arch == "aarch64":
        platform_tag = "linux-arm64"
    else:
        print("[DEBUG] Unsupported OS or architecture.")
        print("[DEBUG] available parameters:")
        print("[DEBUG] version: e.g., v1.0.0")
        print("[DEBUG] os: [win, macos, linux, android]")
        print("[DEBUG] arch: [aarch64, x86_64]")
        sys.exit(1)

    return platform_tag


def resolve_deps_root() -> Path:
    deps_dir = working_dir / "deps"

    direct_bin = deps_dir / "bin"
    direct_agent = deps_dir / "share" / "MaaAgentBinary"
    if direct_bin.exists() and direct_agent.exists():
        return deps_dir

    for child in sorted(deps_dir.iterdir()):
        if not child.is_dir():
            continue
        child_bin = child / "bin"
        child_agent = child / "share" / "MaaAgentBinary"
        if child_bin.exists() and child_agent.exists():
            return child

    print('[DEBUG] Please download the MaaFramework to "deps" first.')
    print('[DEBUG] 请先下载 MaaFramework 到 "deps"。')
    sys.exit(1)


def install_deps():
    deps_root = resolve_deps_root()
    deps_bin = deps_root / "bin"
    deps_agent = deps_root / "share" / "MaaAgentBinary"

    if os_name == "android":
        shutil.copytree(
            deps_bin,
            install_path,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            deps_agent,
            install_path / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
    else:
        runtime_native_dir = (
            install_path / "runtimes" / get_dotnet_platform_tag() / "native"
        )
        shutil.copytree(
            deps_bin,
            runtime_native_dir,
            ignore=shutil.ignore_patterns(
                "*MaaDbgControlUnit*",
                "*MaaThriftControlUnit*",
                "*MaaRpc*",
                "*MaaHttp*",
                "plugins",
                "*.node",
                "*MaaPiCli*",
            ),
            dirs_exist_ok=True,
        )
        shutil.copytree(
            deps_agent,
            install_path / "libs" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            deps_bin / "plugins",
            install_path / "plugins" / get_dotnet_platform_tag(),
            dirs_exist_ok=True,
        )

        if os_name == "win":
            shared_lib_patterns = ("*.dll",)
        elif os_name == "linux":
            shared_lib_patterns = ("*.so", "*.so.*")
        elif os_name == "macos":
            shared_lib_patterns = ("*.dylib",)
        else:
            shared_lib_patterns = tuple()

        for pattern in shared_lib_patterns:
            for lib_file in deps_bin.glob(pattern):
                if lib_file.is_file():
                    shutil.copy2(lib_file, install_path / lib_file.name)

        toolkit_name = {
            "win": "MaaToolkit.dll",
            "linux": "libMaaToolkit.so",
            "macos": "libMaaToolkit.dylib",
        }.get(os_name)
        if toolkit_name:
            toolkit_sources = [
                deps_bin / toolkit_name,
                runtime_native_dir / toolkit_name,
            ]
            for toolkit_file in toolkit_sources:
                if toolkit_file.exists():
                    shutil.copy2(toolkit_file, install_path / toolkit_name)
                    break


def ensure_embedded_python_pth() -> None:
    """为内置 Python 运行时生成版本化 ._pth，避免解释器初始化失败。"""
    if os_name != "win":
        return

    runtime_dir = resolve_windows_python_runtime_dir()
    if not runtime_dir.exists():
        return

    version_tags: list[int] = []
    for dll in runtime_dir.glob("python*.dll"):
        match = re.fullmatch(r"python(\d{3})\.dll", dll.name.lower())
        if match:
            version_tags.append(int(match.group(1)))

    if not version_tags:
        print(
            "[DEBUG] Skip ._pth generation: "
            f"no pythonXYZ.dll found in {runtime_dir}"
        )
        return

    py_tag = str(max(version_tags))
    pth_file = runtime_dir / f"python{py_tag}._pth"

    stdlib_entries: list[str] = []
    std_zip = f"python{py_tag}.zip"
    if (runtime_dir / std_zip).exists():
        stdlib_entries.append(std_zip)
    if (runtime_dir / "base_library.zip").exists():
        stdlib_entries.append("base_library.zip")

    if std_zip not in stdlib_entries:
        raise RuntimeError(
            "Windows embedded runtime is incomplete: "
            f"missing required stdlib zip {std_zip} in {runtime_dir}."
        )

    pth_content = "\n".join([*stdlib_entries, ".", "import site", ""])
    pth_file.write_text(pth_content, encoding="utf-8", newline="\n")
    print(f"[DEBUG] Generated embedded python pth: {pth_file}")


def ensure_windows_embedded_python_runtime() -> None:
    """确保 Windows 包内置 Python 运行时完整（launcher+stdlib+关键扩展模块）。"""
    if os_name != "win":
        return

    runtime_dir = resolve_windows_python_runtime_dir()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    version_tags: list[int] = []
    for dll in runtime_dir.glob("python*.dll"):
        match = re.fullmatch(r"python(\d{3})\.dll", dll.name.lower())
        if match:
            version_tags.append(int(match.group(1)))

    if not version_tags:
        raise RuntimeError(
            f"Cannot detect pythonXYZ.dll in {runtime_dir}. Embedded runtime cannot be prepared."
        )

    py_tag = str(max(version_tags))
    py_major = py_tag[0]
    py_minor = py_tag[1:]
    py_ver = f"{py_major}.{py_minor}.0"

    if arch == "x86_64":
        embed_arch = "amd64"
    elif arch == "aarch64":
        embed_arch = "arm64"
    else:
        raise RuntimeError(f"Unsupported windows arch for embedded python: {arch}")

    std_zip = f"python{py_tag}.zip"
    required_files = ["python.exe", std_zip, "_ctypes.pyd"]
    missing_files = [name for name in required_files if not (runtime_dir / name).exists()]

    if missing_files:
        embed_zip = f"python-{py_ver}-embed-{embed_arch}.zip"
        embed_url = f"https://www.python.org/ftp/python/{py_ver}/{embed_zip}"
        print(
            "[DEBUG] Incomplete embedded runtime, missing "
            f"{missing_files}. Downloading full embeddable package: {embed_url}"
        )

        tmp_zip = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_zip = Path(tmp.name)
            urllib.request.urlretrieve(embed_url, tmp_zip)

            with zipfile.ZipFile(tmp_zip, "r") as zf:
                zf.extractall(runtime_dir)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Failed to prepare embedded Python runtime. "
                f"URL: {embed_url}, error: {exc}"
            ) from exc
        finally:
            if tmp_zip and tmp_zip.exists():
                tmp_zip.unlink(missing_ok=True)

        missing_after = [name for name in required_files if not (runtime_dir / name).exists()]
        if missing_after:
            raise RuntimeError(
                "Embedded Python runtime is still incomplete after download, "
                f"missing: {missing_after}"
            )


def detect_windows_python_runtime_tag(runtime_dir: Path) -> str:
    """从 runtime 目录中解析 pythonXYZ.dll 对应的 XYZ 版本号。"""
    version_tags: list[int] = []
    for dll in runtime_dir.glob("python*.dll"):
        match = re.fullmatch(r"python(\d{3})\.dll", dll.name.lower())
        if match:
            version_tags.append(int(match.group(1)))

    if not version_tags:
        raise RuntimeError(
            f"Cannot detect pythonXYZ.dll in {runtime_dir}."
        )

    return str(max(version_tags))


def get_windows_pip_target(runtime_dir: Path) -> tuple[str, str, str]:
    """返回 pip 跨平台安装所需的 platform/python-version/abi。"""
    py_tag = detect_windows_python_runtime_tag(runtime_dir)
    py_major = py_tag[0]
    py_minor = py_tag[1:]

    if arch == "x86_64":
        pip_platform = "win_amd64"
    elif arch == "aarch64":
        pip_platform = "win_arm64"
    else:
        raise RuntimeError(f"Unsupported windows arch for pip target: {arch}")

    pip_python_version = f"{py_major}.{py_minor}"
    pip_abi = f"cp{py_tag}"
    return pip_platform, pip_python_version, pip_abi


def install_agent_python_dependencies() -> None:
    """将 agent 依赖安装到包内 Python 运行时，避免依赖宿主环境。"""
    requirements_file = working_dir / "agent" / "requirements.txt"
    if not requirements_file.exists():
        print(f"[DEBUG] Skip agent dependency install: {requirements_file} not found")
        return

    if os_name != "win":
        print("[DEBUG] Skip agent dependency install: only enabled for win packaging")
        return

    runtime_dir = resolve_windows_python_runtime_dir()
    runtime_python = runtime_dir / "python.exe"
    if not runtime_python.exists():
        raise RuntimeError(
            "Cannot install agent dependencies: "
            f"missing bundled python executable at {runtime_python}"
        )

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--no-compile",
        "--upgrade",
        "--target",
        str(runtime_dir),
    ]

    # CI 在 ubuntu 上构建 Windows 包时，需要按目标平台下载 wheel，避免混入 Linux 产物。
    if os.name != "nt":
        pip_platform, pip_python_version, pip_abi = get_windows_pip_target(runtime_dir)
        cmd.extend(
            [
                "--only-binary",
                ":all:",
                "--platform",
                pip_platform,
                "--implementation",
                "cp",
                "--python-version",
                pip_python_version,
                "--abi",
                pip_abi,
            ]
        )
        print(
            "[DEBUG] Cross-platform dependency install target: "
            f"platform={pip_platform}, py={pip_python_version}, abi={pip_abi}"
        )

    cmd.extend(["-r", str(requirements_file)])

    print(f"[DEBUG] Installing agent dependencies into {runtime_dir}")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            "Failed to install agent dependencies into bundled runtime.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )

    strenum_module = runtime_dir / "strenum.py"
    strenum_pkg_init = runtime_dir / "strenum" / "__init__.py"
    if not strenum_module.exists() and not strenum_pkg_init.exists():
        strenum_module.write_text(
            (
                "from enum import Enum\n"
                "\n"
                "class StrEnum(str, Enum):\n"
                "    pass\n"
            ),
            encoding="utf-8",
            newline="\n",
        )
        print("[DEBUG] Injected fallback strenum.py into bundled runtime")

    print("[DEBUG] Agent dependencies installed successfully")



def install_resource():
    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )

    assets_index_dir = working_dir / "assets" / "index"
    if assets_index_dir.exists() and assets_index_dir.is_dir():
        shutil.copytree(
            assets_index_dir,
            install_path / "resource" / "index",
            dirs_exist_ok=True,
        )

    install_resource_path = install_path / "resource"
    base_path = install_resource_path / "base"

    def merge_into_base(src_name: str, dst_name: str) -> None:
        src = install_resource_path / src_name
        if not src.exists() or not src.is_dir():
            return
        dst = base_path / dst_name
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        shutil.rmtree(src)

    merge_into_base("image", "image")
    merge_into_base("model", "model")
    merge_into_base("pipeline", "pipeline")

    local_mah_res_candidates = [
        working_dir / "mah_res",
        working_dir.parent / "mah_res",
    ]
    local_mah_res = next(
        (
            path
            for path in local_mah_res_candidates
            if path.exists() and path.is_dir()
        ),
        None,
    )
    if local_mah_res:
        local_index = local_mah_res / "index"
        if local_index.exists() and local_index.is_dir():
            shutil.copytree(
                local_index,
                install_resource_path / "index",
                dirs_exist_ok=True,
            )

        local_image = local_mah_res / "image"
        if local_image.exists() and local_image.is_dir():
            shutil.copytree(
                local_image,
                base_path / "image",
                dirs_exist_ok=True,
            )

        local_model = local_mah_res / "model"
        if local_model.exists() and local_model.is_dir():
            shutil.copytree(
                local_model,
                base_path / "model",
                dirs_exist_ok=True,
            )

        local_pipeline = local_mah_res / "pipeline"
        if local_pipeline.exists() and local_pipeline.is_dir():
            shutil.copytree(
                local_pipeline,
                base_path / "pipeline",
                dirs_exist_ok=True,
            )

    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    assets_icon_path = working_dir / "assets" / "icon.png"
    if assets_icon_path.exists():
        shutil.copy2(assets_icon_path, install_path / "icon.png")

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    if os_name == "win":
        runtime_dir = resolve_windows_python_runtime_dir()
        runtime_python = runtime_dir / "python.exe"
        if not runtime_python.exists():
            raise RuntimeError(
                "Windows package expects bundled python.exe, "
                f"but it is missing in {runtime_dir}."
            )

        runtime_python_rel = runtime_python.relative_to(install_path).as_posix()
        internal_python = f"./{runtime_python_rel}"

        def _apply_agent_exec(agent_obj):
            if isinstance(agent_obj, dict):
                agent_obj["child_exec"] = internal_python

        agents = interface.get("agent")
        if isinstance(agents, dict):
            _apply_agent_exec(agents)
        elif isinstance(agents, list):
            for agent_obj in agents:
                _apply_agent_exec(agent_obj)

        print(f"[DEBUG] Windows agent child_exec resolved to: {internal_python}")

    original_resource_version = (
        resource_version_override
        or interface.get("resource_version")
        or interface.get("version")
        or version
    )
    interface["resource_version"] = original_resource_version
    interface["version"] = version

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )

    if not (install_path / "icon.png").exists():
        fallback_icons = [
            working_dir / "assets" / "icon.png",
            working_dir / "icon.png",
            install_path / "app" / "assets" / "icons" / "logo.png",
            install_path / "_internal" / "app" / "assets" / "icons" / "logo.png",
        ]
        for fallback_icon in fallback_icons:
            if fallback_icon.exists():
                shutil.copy2(fallback_icon, install_path / "icon.png")
                break

    maa_option_src = working_dir / "config" / "maa_option.json"
    if maa_option_src.exists():
        install_config_dir = install_path / "config"
        install_config_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(maa_option_src, install_config_dir / "maa_option.json")


def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
    )


def install_data():
    source_data_dir = working_dir / "data"
    target_data_dir = install_path / "data"

    if source_data_dir.exists():
        shutil.copytree(
            source_data_dir,
            target_data_dir,
            dirs_exist_ok=True,
        )
    else:
        target_data_dir.mkdir(parents=True, exist_ok=True)
        (target_data_dir / "auto_combat").mkdir(parents=True, exist_ok=True)


def deduplicate_case_insensitive_files_for_windows() -> None:
    """去除 Windows 包中仅大小写不同的重复文件，避免出现双份 DLL。"""
    if os_name != "win":
        return

    removed: list[str] = []

    for current_dir, _, file_names in os.walk(install_path):
        if not file_names:
            continue

        grouped: dict[str, list[Path]] = {}
        for file_name in file_names:
            path_obj = Path(current_dir) / file_name
            grouped.setdefault(file_name.lower(), []).append(path_obj)

        for _, paths in grouped.items():
            if len(paths) <= 1:
                continue

            # 优先保留更接近小写命名的文件，避免 Python 运行时 DLL 重复。
            keep = min(
                paths,
                key=lambda p: (sum(ch.isupper() for ch in p.name), p.name.lower(), p.name),
            )
            for dup in paths:
                if dup == keep:
                    continue
                dup.unlink(missing_ok=True)
                removed.append(str(dup.relative_to(install_path)).replace("\\", "/"))

    if removed:
        print("[DEBUG] Removed case-insensitive duplicate files:")
        for item in removed:
            print(f"[DEBUG]   - {item}")


if __name__ == "__main__":
    install_deps()
    ensure_windows_embedded_python_runtime()
    ensure_embedded_python_pth()
    install_agent_python_dependencies()
    install_resource()
    install_chores()
    install_agent()
    install_data()
    deduplicate_case_insensitive_files_for_windows()

    print(f"[DEBUG] Install to {install_path} successfully.")
