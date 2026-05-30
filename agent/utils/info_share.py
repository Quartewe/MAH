from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import json
from . import logger

class InfoShare:
    is_first_run = False
    combat_set = False
    select_support_fast = False
    auto_combat_mode = False
    current_lang = ""
    show_support = False
    counter = 1
    leader_pos = [] 
    IGNORE_LIST = ["ATK", "DEF", "HP", "SP", "CD", "Energy", "Shield", "Damage", "Heal", "Buff", "Debuff", "进行度", "進行度", "COMPELETED", "x100"]
    drink_times = {
        "All": 0,
        "Half": 0,
        "Mini": 0,
        "Ranpoil": 0
    }

info_share= InfoShare()

@AgentServer.custom_action("InfoShareAction")
class InfoShareAction(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        param = json.loads(argv.custom_action_param)

        if isinstance(param, dict):
            for key, value in param.items():
                if hasattr(info_share, key):
                    raw_value = getattr(info_share, key, None)
                    logger.info(f"存在键 {key}")

                    if isinstance(value, type(raw_value)):
                        logger.info(f"类型匹配, 更新 {key} 的值为 {value}")
                        setattr(info_share, key, value)
                    else:
                        logger.warning(f"类型不匹配, 无法更新 {key} 的值. 期望类型: {type(raw_value)}, 实际类型: {type(value)}")

                else:
                    logger.warning(f"InfoShare 中不存在键 {key}, 无法更新")
        else:
            logger.warning("参数格式错误, 期望一个字典")
        return True
