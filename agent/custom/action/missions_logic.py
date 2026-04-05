from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
from utils import data_io, timeout_mgr, proj_path


@AgentServer.custom_action("MissionLogic")
class MissionLogic(CustomAction):
    def __init__(self):
        super().__init__()
        self.state = data_io.read_data(proj_path.STATE_FILE)

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):    
            return False
        
        match argv.node_name:
            case "CheckWeeklyMissions.Stop":
                first_key, first_value = next(iter(self.state.items()))
                if first_value["completed"] == True:
                    print("[DEBUG]每周任务已完成，跳过")
                    timeout_mgr.stop_monitoring(argv.node_name)
                    return True
                else:
                    print("[DEBUG]每周任务未完成，继续监控")
                    return False


        timeout_mgr.stop_monitoring(argv.node_name)
        return True