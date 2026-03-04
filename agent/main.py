import sys
from maa.agent.agent_server import AgentServer
if AgentServer:
    print("[DEBUG] MAA 框架导入成功")
from debug import Debug
if Debug:
    print("[DEBUG] Debug 导入成功")
from weekly_mission import WeeklyMission
if WeeklyMission:
    print("[DEBUG] WeeklyMission 导入成功")
from missions_logic import MissionLogic
if MissionLogic:
    print("[DEBUG] MissionLogic 导入成功")
from resource_record import ResourceRecord
if ResourceRecord:
    print("[DEBUG] ResourceRecord 导入成功")
from recutils import TraverseMatch, GroupAvatarInfo
if TraverseMatch and GroupAvatarInfo:
    print("[DEBUG] TraverseMatch 和 GroupAvatarInfo 导入成功")

def main():
    if len(sys.argv) >= 2:
        Agent_Identifier = sys.argv[1]
    else:
        Agent_Identifier = "MHA"

    print(f"[DEBUG] AgentServer 正在启动，频道 ID 为: {Agent_Identifier}")

    AgentServer.start_up(Agent_Identifier)

    print("[DEBUG] 服务器已启动，等待 MAA 任务触发... (按 Ctrl+C 停止)")

    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
