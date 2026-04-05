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
            print("[DEBUG]GoBack 返回识别结果:", back_res.best_result)
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
                print("[DEBUG]GoBack 点击返回按钮")
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
                print("[DEBUG]GoBack 加载识别结果:", loading_res.best_result)

                if last_try and not back_res.best_result:
                    print("[DEBUG] 返回成功")
                    return True
                else: 
                    print("[DEBUG] 仍在加载，继续等待")
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
                    print("[DEBUG]GoBack 加载识别结果:", loading_res.best_result)
                    time.sleep(1)

                    if not loading_res.best_result:
                        print("[DEBUG] 进入最后一次尝试模式")
                        last_try = True
                        break

            if not back_res.best_result and not loading_res.best_result:
                print("[DEBUG] 返回成功")
                return True

            i += 1
        print("[DEBUG]GoBack 尝试 15 次后仍未返回")
        return False