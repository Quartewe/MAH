from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import actutils


@AgentServer.custom_action("Debug")
class Debug(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        match argv.node_name:
            case "Debug.OCR":
                actutils.data_io.organize_ocr_log(argv.node_name, argv.reco_detail)

            case "Debug.Match":
                # debug
                print(f"[DEBUG] {argv.reco_detail}")
                #
            case "Debug.Do":    
                context.tasker.controller.post_swipe(330,550,330,15,500).wait()
            case _:
                # debug
                print(f"[DEBUG] {argv.node_name}")
                #

        return True
