from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
import actutils


@AgentServer.custom_action("MissionLogic")
class MissionLogic(CustomAction):
    def __init__(self):
        super().__init__()
        self.state = None

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if actutils.timeout_mgr.check_timeout(argv.node_name):    
            return False
        
        self.state = actutils.data_io.read_data()
        # 输出日志
        actutils.data_io.organize_ocr_log(argv.node_name, argv.reco_detail)

        # 选择任务
        match argv.node_name:
            case "ShowSupporterScreen.Entry":
                mission_status = self.state["missions"]["显示支援者组队画面"][
                    "completed"
                ]
                # debug
                print(f"[DEBUG] {argv.node_name}")
                print(f"[DEBUG] 显示支援者组队画面 {mission_status}")
                #
                actutils.timeout_mgr.stop_monitoring(argv.node_name)
                return not mission_status

            case "Dungeon.Entry":
                mission_status = self.state["missions"]["完成攻略3次地城"]["completed"]
                # debug
                print(f"[DEBUG] {argv.node_name}")
                print(f"[DEBUG] 完成攻略3次地城 {mission_status}")
                #
                actutils.timeout_mgr.stop_monitoring(argv.node_name)
                return not mission_status
