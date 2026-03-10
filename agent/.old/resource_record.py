from maa.custom_recognition import CustomRecognition
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
import actutils
import re


@AgentServer.custom_action("ResourceRecord")
class ResourceRecord(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if actutils.timeout_mgr.check_timeout(argv.node_name):    
            return False

        state = actutils.data_io.read_data()
        now = datetime.now().timestamp()


        match argv.node_name:
            case "ResourceRecord.DP":
                if argv.reco_detail.filtered_results:
                    num = len(argv.reco_detail.filtered_results)
                    # debug
                    print(f"[DEBUG] Current DP Data:{num} / 3")
                    #
                    state["resources"]["DP"]["value"] = num
                    state["resources"]["DP"]["last_updated"] = now
                    actutils.timeout_mgr.stop_monitoring(argv.node_name)
            case "ResourceRecord.AP":
                if argv.reco_detail.filtered_results:
                    raw_text = argv.reco_detail.filtered_results[0].text
                    nums = re.findall(r"(\d+)", raw_text)
                    # debug
                    print(f"[DEBUG] Current AP Data:{nums[0]} / {nums[1]}")
                    #
                    if len(nums) >= 2:
                        state["resources"]["AP"]["value"] = int(nums[0])
                        state["resources"]["AP"]["upper_limit"] = int(nums[1])
                        state["resources"]["AP"]["last_updated"] = now
                    actutils.timeout_mgr.stop_monitoring(argv.node_name)
            case "ResourceRecord.Stone":
                if argv.reco_detail.filtered_results:
                    raw = argv.reco_detail.filtered_results[0].text.replace(",", "")
                    state["resources"]["Stone"] = int(raw)
                    # debug
                    print("[DEBUG] Current Stone:", raw)
                    #
                    actutils.timeout_mgr.stop_monitoring(argv.node_name)

            case "ResourceRecord.RF":
                if argv.reco_detail.filtered_results:
                    raw = argv.reco_detail.filtered_results[0].text.replace(",", "")
                    state["resources"]["RF"] = int(raw)
                    # debug
                    print("[DEBUG] Current Rainbow Fragment:", raw)
                    #
                    actutils.timeout_mgr.stop_monitoring(argv.node_name)

        actutils.data_io.write_data(state)

        print("[DEBUG] Record mission run accomplished")
        return True
