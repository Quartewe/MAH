from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import json
import actutils

@AgentServer.custom_action("Formation")
class Formation(CustomAction):
    ...
    # TODO: 实现自动编队功能,由用户传入的作业参数决定编队内容