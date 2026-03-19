import sys
import os

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
