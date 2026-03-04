from maa.custom_recognition import CustomRecognition
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
import actutils
import re

# 在这里比较数据

@AgentServer.custom_action("SelectSupport")
class SelectSupport(CustomAction):
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
        
        if argv.reco_detail
        matched = []
        
        while not argv.reco_detail.box:
            current_image = context.tasker.controller.cached_image()
            actutils.act_mgr.swipe(context, [330, 530, 10, 10],[330, 15, 10, 10], 0.5, timing='ease_out_quad')
            context.run_recognition_direct(
                "GroupAvatarInfo",
                param={"template_type": "A"},
                image=current_image
            )
        
        actutils.timeout_mgr.stop_monitoring(argv.node_name)
        return True