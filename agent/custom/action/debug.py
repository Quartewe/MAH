from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils import data_io


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
                data_io.organize_ocr_log(argv.node_name, argv.reco_detail)

            case "Debug.Match":
                # debug
                print(f"[DEBUG] {argv.reco_detail}")
                #
            case "Debug.Do": 
                import time
                context.tasker.controller.post_touch_down(330, 550)
                print(f"[DEBUG] Touch down at (330, 550)")
                time.sleep(0.5)
                context.tasker.controller.post_touch_move(330, 15).wait()
                print(f"[DEBUG] Touch move to (330, 15)")
                time.sleep(1)
                context.tasker.controller.post_touch_up()
                print(f"[DEBUG] Touch up")
            case _:
                # debug
                print(f"[DEBUG] {argv.node_name}")
                #

        return True
