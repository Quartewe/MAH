from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils import timeout_mgr, info_share, logger


@AgentServer.custom_action("MissionLogic")
class MissionLogic(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        if timeout_mgr.check_timeout(argv.node_name):    
            return False

        match argv.node_name:
            case "CheckWeeklyMissions.Stop":
                if info_share.is_first_run:
                    logger.info("[DEBUG]为本周第一次运行, 初始化每周任务状态")
                    info_share.show_support = False
                if info_share.show_support:
                    logger.info("[DEBUG]每周任务已完成，跳过")
                    timeout_mgr.stop_monitoring(argv.node_name)
                    return True
                else:
                    logger.info("[DEBUG]每周任务未完成，继续监控")
                    return False
            case "ShowSupporterScreen.SetRun":
                info_share.is_first_run = False

        timeout_mgr.stop_monitoring(argv.node_name)
        return True
    
