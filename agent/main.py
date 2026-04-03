import sys
import os
import builtins
from datetime import datetime
from pathlib import Path
from threading import Lock


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

# 为打包目录与源码目录同时注入运行时路径，避免找不到 maa 模块
def _setup_runtime_paths() -> None:
    project_root = Path(__file__).resolve().parent.parent
    agent_path = project_root / "agent"
    internal_path = project_root / "_internal"

    for path in (agent_path, internal_path, project_root):
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)

    if internal_path.exists():
        internal_str = str(internal_path)

        current_pythonpath = os.environ.get("PYTHONPATH", "")
        pythonpath_entries = current_pythonpath.split(os.pathsep) if current_pythonpath else []
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
                internal_str if not current_path else f"{internal_str}{os.pathsep}{current_path}"
            )

        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(internal_str)


_setup_runtime_paths()

from maa.agent.agent_server import AgentServer
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
    print(f"[DEBUG] AgentServer 正在启动，频道 ID 为: {Agent_Identifier}")

    AgentServer.start_up(Agent_Identifier)

    print("[DEBUG] 服务器已启动，等待 MAA 任务触发... (按 Ctrl+C 停止)")

    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
