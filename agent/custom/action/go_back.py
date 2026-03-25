from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import json
import time


@AgentServer.custom_action("GoBack")
class GoBack(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        
        param = json.loads(argv.custom_action_param)
        i = 0
        last_try = False
        while i < 15:
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            back_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "post_wait_freezes":2000,
                        "recognition": {
                            "param": {
                                "roi": [4,12,301,102],
                                "expected": param,
                            },
                        }
                    }
                }
            )
            print("[DEBUG]GoBack back_res:", back_res.best_result)
            if back_res.best_result:
                context.run_action(
                    "UtilsClick",
                    pipeline_override={
                        "UtilsClick":{
                            "action":{
                                "param":{
                                    "target": back_res.best_result.box
                                }
                            }
                        }
                    }
                )
                print("[DEBUG]GoBack click back button")
            else:
                loading_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "post_wait_freezes":2000,
                        "recognition": {
                            "param": {
                                "roi": [9,572,522,149],
                                "expected": "LOADING",
                                },
                            }
                        }
                    }
                )
                print("[DEBUG]GoBack loading_res:", loading_res.best_result)

                if last_try and not back_res.best_result:
                    print("[DEBUG] Successfully go back")
                    return True
                else: 
                    print("[DEBUG] Still loading, keep waiting")
                    last_try = False

                while loading_res.best_result:
                    context.tasker.controller.post_screencap().wait()
                    current_image = context.tasker.controller.cached_image
                    loading_res = context.run_recognition(
                    "UtilsOCR",
                    current_image,
                    pipeline_override={
                        "UtilsOCR": {
                            "post_wait_freezes":2000,
                            "recognition": {
                                "param": {
                                    "roi": [9,572,522,149],
                                    "expected": "LOADING",
                                    },
                                }
                            }
                        }
                    )
                    print("[DEBUG]GoBack loading_res:", loading_res.best_result)
                    time.sleep(1)

                    if not loading_res.best_result:
                        print("[DEBUG] Last try mode")
                        last_try = True
                        break
                    
            i += 1
        print("[DEBUG]GoBack failed to go back after 15 attempts")
        return False