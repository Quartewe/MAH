import sys
import os
import builtins
import re
import shutil
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional, Tuple


_ORIGINAL_PRINT = builtins.print
_PRINT_LOCK = Lock()


def _setup_backend_log_print() -> None:
    project_root = Path(__file__).resolve().parent.parent
    log_dir = project_root / "debug"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"

    def _patched_print(*args, **kwargs):
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        _ORIGINAL_PRINT(timestamp, *args, **kwargs)

        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        message = sep.join(str(arg) for arg in args)
        if end is None:
            end = ""

        with _PRINT_LOCK:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"{timestamp} {message}{end}")

    builtins.print = _patched_print


_setup_backend_log_print()


def _append_bootstrap_error(title: str, detail: str) -> None:
    """在最早期导入失败时，兜底写入 backend.log，避免 UI 侧吞掉 stderr。"""
    try:
        project_root = Path(__file__).resolve().parent.parent
        log_dir = project_root / "debug"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "backend.log"
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp} [BOOTSTRAP_ERROR] {title}\n{detail}\n")
    except Exception:
        # 兜底日志失败不应再次中断启动流程
        pass


print("[DEBUG] Agent 启动引导开始")


def _detect_internal_python_version(internal_path: Path) -> Optional[Tuple[int, int]]:
    """检测 _internal 目录期望的 Python 主次版本。"""
    if not internal_path.exists():
        return None

    # Windows: python312.dll / python311.dll
    for dll in internal_path.glob("python*.dll"):
        match = re.fullmatch(r"python(\d)(\d{2})\.dll", dll.name.lower())
        if match:
            return int(match.group(1)), int(match.group(2))

    # Linux/macOS: libpython3.12.so / libpython3.12.dylib
    for lib in internal_path.glob("libpython*.*"):
        match = re.search(r"libpython(\d)\.(\d+)", lib.name.lower())
        if match:
            return int(match.group(1)), int(match.group(2))

    return None


def _probe_python_version(python_exec: str) -> Optional[Tuple[int, int, str]]:
    """探测解释器版本，返回 (major, minor, executable)。"""
    try:
        proc = subprocess.run(
            [python_exec, "-c", "import sys;print(sys.version_info[0],sys.version_info[1],sys.executable)"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None

    if proc.returncode != 0:
        return None

    parts = proc.stdout.strip().split(maxsplit=2)
    if len(parts) != 3:
        return None

    try:
        return int(parts[0]), int(parts[1]), parts[2]
    except ValueError:
        return None


def _find_matching_python(expected: Tuple[int, int]) -> Optional[str]:
    """查找与期望版本一致的 Python 可执行文件。"""
    exp_major, exp_minor = expected

    # 1) Windows py launcher
    if os.name == "nt":
        py_launcher = shutil.which("py")
        if py_launcher:
            try:
                proc = subprocess.run(
                    [
                        py_launcher,
                        f"-{exp_major}.{exp_minor}",
                        "-c",
                        "import sys;print(sys.executable)",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0:
                    exe = proc.stdout.strip()
                    if exe and Path(exe).exists():
                        return exe
            except OSError:
                pass

    # 2) PATH 常见命令
    command_candidates = [
        f"python{exp_major}.{exp_minor}",
        f"python{exp_major}{exp_minor}",
        "python3",
        "python",
    ]
    for cmd in command_candidates:
        path = shutil.which(cmd)
        if not path:
            continue
        probed = _probe_python_version(path)
        if not probed:
            continue
        major, minor, executable = probed
        if (major, minor) == expected:
            return executable

    # 3) Windows 常见安装路径
    if os.name == "nt":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            guessed = (
                Path(localappdata)
                / "Programs"
                / "Python"
                / f"Python{exp_major}{exp_minor}"
                / "python.exe"
            )
            if guessed.exists():
                return str(guessed)

    return None


def _relaunch_with_python(python_exec: str) -> None:
    """使用匹配版本解释器原地重启当前进程，保持 Agent 启动链路一致。"""
    env = os.environ.copy()
    env["MAH_AGENT_RELAUNCHED"] = "1"
    args = [python_exec, str(Path(__file__).resolve()), *sys.argv[1:]]
    os.execve(python_exec, args, env)

# 为打包目录与源码目录同时注入运行时路径，避免找不到 maa 模块
def _setup_runtime_paths() -> Tuple[Optional[Tuple[int, int]], bool]:
    project_root = Path(__file__).resolve().parent.parent
    agent_path = project_root / "agent"
    internal_path = project_root / "_internal"
    current_py = (sys.version_info.major, sys.version_info.minor)
    expected_py = _detect_internal_python_version(internal_path)
    internal_injected = False

    for path in (agent_path, project_root):
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)

    if internal_path.exists():
        internal_str = str(internal_path)

        # 只有版本匹配时才注入 _internal，避免不同 Python 版本加载到错误二进制模块。
        should_inject_internal = expected_py is None or expected_py == current_py
        if should_inject_internal:
            if internal_str not in sys.path:
                sys.path.insert(0, internal_str)

            current_pythonpath = os.environ.get("PYTHONPATH", "")
            pythonpath_entries = (
                current_pythonpath.split(os.pathsep) if current_pythonpath else []
            )
            if internal_str not in pythonpath_entries:
                os.environ["PYTHONPATH"] = (
                    internal_str
                    if not current_pythonpath
                    else f"{internal_str}{os.pathsep}{current_pythonpath}"
                )

            current_path = os.environ.get("PATH", "")
            path_entries = current_path.split(os.pathsep) if current_path else []
            if internal_str not in path_entries:
                os.environ["PATH"] = (
                    internal_str
                    if not current_path
                    else f"{internal_str}{os.pathsep}{current_path}"
                )

            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(internal_str)

            internal_injected = True
        else:
            print(
                "[WARN] 检测到 _internal 期望 Python "
                f"{expected_py[0]}.{expected_py[1]}，当前为 {current_py[0]}.{current_py[1]}，"
                "已暂不注入 _internal，后续将尝试自动切换解释器。"
            )

    return expected_py, internal_injected


_expected_python, _internal_injected = _setup_runtime_paths()

try:
    from maa.agent.agent_server import AgentServer
except ImportError as exc:
    current_py = (sys.version_info.major, sys.version_info.minor)
    already_relaunched = os.environ.get("MAH_AGENT_RELAUNCHED") == "1"

    if (
        _expected_python is not None
        and _expected_python != current_py
        and not already_relaunched
    ):
        matched_python = _find_matching_python(_expected_python)
        if matched_python:
            print(
                "[WARN] 当前解释器与内置运行时不匹配，"
                f"准备切换到 Python {_expected_python[0]}.{_expected_python[1]}: {matched_python}"
            )
            _relaunch_with_python(matched_python)

    expected_text = (
        f"{_expected_python[0]}.{_expected_python[1]}" if _expected_python else "未知"
    )
    import_error_text = (
        "无法导入 maa。"
        f" 当前 Python: {current_py[0]}.{current_py[1]}，"
        f"_internal 期望 Python: {expected_text}。"
        "请安装匹配版本 Python，或在当前 Python 环境安装与之匹配的 maa 依赖。"
    )
    _append_bootstrap_error(import_error_text, traceback.format_exc())
    print(f"[ERROR] {import_error_text}")
    raise ImportError(
        import_error_text
    ) from exc

print("[DEBUG] MAA 框架导入成功")

# 导入 custom 包，触发所有 @AgentServer 装饰器注册
import custom  # noqa: F401
print("[DEBUG] 所有 custom action/recognition 已注册")


def main():
    if len(sys.argv) >= 2:
        Agent_Identifier = sys.argv[1]
    else:
        Agent_Identifier = "MAH"
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"[DEBUG] AgentServer 正在启动，通道 ID 为: {Agent_Identifier}")

    AgentServer.start_up(Agent_Identifier)

    print("[DEBUG] 服务器已启动，等待 MAA 任务触发... (按 Ctrl+C 停止)")

    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
