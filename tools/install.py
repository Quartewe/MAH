from pathlib import Path

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

# the first parameter is self name
if sys.argv.__len__() < 4:
    print("[DEBUG] Usage: python install.py <version> <os> <arch>")
    print("[DEBUG] Example: python install.py v1.0.0 win x86_64")
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


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print('[DEBUG] Please download the MaaFramework to "deps" first.')
        print('[DEBUG] 请先下载 MaaFramework 到 "deps"。')
        sys.exit(1)

    if os_name == "android":
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
    else:
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path / "runtimes" / get_dotnet_platform_tag() / "native",
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
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "libs" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "bin" / "plugins",
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
            for lib_file in (working_dir / "deps" / "bin").glob(pattern):
                if lib_file.is_file():
                    shutil.copy2(lib_file, install_path / lib_file.name)



def install_resource():
    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    for interface_file in (working_dir / "assets").glob("interface_*.json"):
        if interface_file.is_file():
            shutil.copy2(interface_file, install_path / interface_file.name)

    assets_icon_path = working_dir / "assets" / "icon.png"
    if assets_icon_path.exists():
        shutil.copy2(assets_icon_path, install_path / "icon.png")

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

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
    install_resource()
    install_chores()
    install_agent()
    install_data()

    print(f"[DEBUG] Install to {install_path} successfully.")
