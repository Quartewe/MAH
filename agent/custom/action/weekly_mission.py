from maa.custom_recognition import CustomRecognition
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
from utils import data_io, mission_mgr, timeout_mgr


@AgentServer.custom_action("WeeklyMission")
class WeeklyMission(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):    
            return False

        # 输出日志
        data_io.organize_ocr_log(argv.node_name, argv.reco_detail)


        success = True
        # 选择任务
        if argv.node_name == "CheckWeeklyMissions.Record":
            # debug
            print("Current mission data:", data_io.read_data()["missions"])
            #
            success = mission_mgr.catch_task(argv.reco_detail.filtered_results)
            if success:
                timeout_mgr.stop_monitoring(argv.node_name)
                
        elif argv.node_name == "CheckWeeklyMissions.AllCompleted":
            success = data_io.set_to_completed()
            # debug
            print("All completed")
            #
            timeout_mgr.stop_monitoring(argv.node_name)

        # 如果是周一且是入口节点，重置任务数据
        if datetime.now().weekday() == 0 and "Entry" in argv.node_name:
            data_io.reset_data(argv.node_name)
            # debug
            print("Monday detected at Entry, reset mission data")
            #
            timeout_mgr.stop_monitoring(argv.node_name)

        print("WeeklyMission run accomplished")
        return success
