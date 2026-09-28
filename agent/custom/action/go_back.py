from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import json
import time
from utils import logger, timeout_mgr


@AgentServer.custom_action("GoBack")
class GoBack(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        try:
            param = json.loads(argv.custom_action_param)
            clicks = 0
            while clicks < 15:
                if context.tasker.stopping or timeout_mgr.check_timeout(argv.node_name):
                    return False

                context.tasker.controller.post_screencap().wait()
                current_image = context.tasker.controller.cached_image
                back_res = context.run_recognition(
                    "UtilsOCR",
                    current_image,
                    pipeline_override={
                        "UtilsOCR": {
                            "recognition": {
                                "param": {"roi": [4, 12, 301, 102], "expected": param}
                            }
                        }
                    },
                )
                if back_res.best_result:
                    result = context.run_action(
                        "UtilsClick",
                        back_res.best_result.box,
                        pipeline_override={
                            "UtilsClick": {
                                "action": {"param": {"target": back_res.best_result.box}}
                            }
                        },
                    )
                    if result is None or not result.success:
                        return False
                    clicks += 1
                    continue

                loading_res = context.run_recognition(
                    "UtilsOCR",
                    current_image,
                    pipeline_override={
                        "UtilsOCR": {
                            "recognition": {
                                "param": {"roi": [9, 572, 522, 148], "expected": "LOADING"}
                            }
                        }
                    },
                )
                if loading_res.best_result:
                    logger.info("仍在加载，继续等待")
                    time.sleep(1)
                    # 下一轮重新截屏，同时检查返回和加载，不能复用加载前的返回结果。
                    continue

                logger.info("返回成功")
                return True

            logger.warning("尝试 15 次后仍未返回")
            return False
        finally:
            timeout_mgr.stop_monitoring(argv.node_name)
