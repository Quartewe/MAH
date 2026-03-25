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

        if info_share.counter < param:
            info_share.counter += 1
            print(f"[Counter] Counter increased to {info_share.counter}")
            return True
        else:
            print(f"[Counter] Counter reached maximum value {param}")
            info_share.counter = 1  # Reset counter for next round
            return False
