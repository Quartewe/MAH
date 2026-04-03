from pathlib import Path
import re

import shutil
import sys

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

    internal_dir = install_path / "_internal"
    if not internal_dir.exists():
        return

    version_tags: list[int] = []
    for dll in internal_dir.glob("python*.dll"):
        match = re.fullmatch(r"python(\d{3})\.dll", dll.name.lower())
        if match:
            version_tags.append(int(match.group(1)))

    if not version_tags:
        print("[DEBUG] Skip ._pth generation: no pythonXYZ.dll found in _internal")
        return

    py_tag = str(max(version_tags))
    pth_file = internal_dir / f"python{py_tag}._pth"

    stdlib_entries: list[str] = []
    std_zip = f"python{py_tag}.zip"
    if (internal_dir / std_zip).exists():
        stdlib_entries.append(std_zip)
    if (internal_dir / "base_library.zip").exists():
        stdlib_entries.append("base_library.zip")

    if not stdlib_entries:
        print(
            "[WARNING] Skip ._pth generation: no stdlib zip found "
            f"(base_library.zip/python{py_tag}.zip)"
        )
        return

    if std_zip not in stdlib_entries:
        print(
            "[WARNING] python stdlib zip missing: "
            f"{std_zip}. Some stdlib modules may be unavailable."
        )

    pth_content = "\n".join([*stdlib_entries, ".", "import site", ""])
    pth_file.write_text(pth_content, encoding="utf-8", newline="\n")
    print(f"[DEBUG] Generated embedded python pth: {pth_file}")



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
        internal_python = "./_internal/python.exe"

        def _apply_agent_exec(agent_obj):
            if isinstance(agent_obj, dict):
                agent_obj["child_exec"] = internal_python

        agents = interface.get("agent")
        if isinstance(agents, dict):
            _apply_agent_exec(agents)
        elif isinstance(agents, list):
            for agent_obj in agents:
                _apply_agent_exec(agent_obj)

        if not (install_path / "_internal" / "python.exe").exists():
            print(
                "[WARNING] Windows package expects ./_internal/python.exe, "
                "but it is missing. Please include embedded python launcher."
            )

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


if __name__ == "__main__":
    install_deps()
    ensure_embedded_python_pth()
    install_resource()
    install_chores()
    install_agent()
    install_data()

    print(f"[DEBUG] Install to {install_path} successfully.")
