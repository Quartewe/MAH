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

# 将 agent 目录加入 sys.path，使 utils/custom 包可被导入
agent_dir = os.path.dirname(os.path.abspath(__file__))
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

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
