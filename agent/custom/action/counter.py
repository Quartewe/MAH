from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils import info_share
import json


@AgentServer.custom_action("Counter")
class Counter(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        param = int(json.loads(argv.custom_action_param))

        current_count = info_share.counter
        print(f"[COUNTER] count={current_count} target={param}", flush=True)

        if current_count < param:
            info_share.counter = current_count + 1
            return True
        else:
            info_share.counter = 1
            return False
