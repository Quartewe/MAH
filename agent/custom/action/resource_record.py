from maa.custom_recognition import CustomRecognition
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
from utils import logger, data_io, timeout_mgr
import re


@AgentServer.custom_action("ResourceRecord")
class ResourceRecord(CustomAction):
    def __init__(self):
        super().__init__()

    @staticmethod
    def _load_resources():
        resources = data_io.read_app_state("resources", {})
        if not isinstance(resources, dict):
            resources = {}
        resources.setdefault("DP", {"value": 0, "last_updated": 0})
        resources.setdefault("AP", {"value": 0, "upper_limit": 0, "last_updated": 0})
        resources.setdefault("Stone", 0)
        resources.setdefault("RF", 0)
        return resources

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):    
            return False

        resources = self._load_resources()
        now = datetime.now().timestamp()


        match argv.node_name:
            case "ResourceRecord.DP":
                if argv.reco_detail.filtered_results:
                    num = len(argv.reco_detail.filtered_results)
                    logger.info(f"当前 DP 数据: {num} / 3")
                    #
                    resources["DP"]["value"] = num
                    resources["DP"]["last_updated"] = now
                    timeout_mgr.stop_monitoring(argv.node_name)
            case "ResourceRecord.AP":
                if argv.reco_detail.filtered_results:
                    raw_text = argv.reco_detail.filtered_results[0].text
                    nums = re.findall(r"(\d+)", raw_text)
                    logger.info(f"当前 AP 数据: {nums[0]} / {nums[1]}")
                    #
                    if len(nums) >= 2:
                        resources["AP"]["value"] = int(nums[0])
                        resources["AP"]["upper_limit"] = int(nums[1])
                        resources["AP"]["last_updated"] = now
                    timeout_mgr.stop_monitoring(argv.node_name)
            case "ResourceRecord.Stone":
                if argv.reco_detail.filtered_results:
                    raw = argv.reco_detail.filtered_results[0].text.replace(",", "")
                    resources["Stone"] = int(raw)
                    logger.info("当前石头:", raw)
                    #
                    timeout_mgr.stop_monitoring(argv.node_name)

            case "ResourceRecord.RF":
                if argv.reco_detail.filtered_results:
                    raw = argv.reco_detail.filtered_results[0].text.replace(",", "")
                    resources["RF"] = int(raw)
                    logger.info("当前虹碎:", raw)
                    #
                    timeout_mgr.stop_monitoring(argv.node_name)

        data_io.write_app_state("resources", resources)

        logger.info("资源记录流程执行完成")
        return True
