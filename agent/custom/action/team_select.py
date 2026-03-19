from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import time
import re
import json


@AgentServer.custom_action("TeamSelect")
class TeamSelect(CustomAction):
    def __init__(self):
        super().__init__()

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        param = json.loads(argv.custom_action_param)
        if not param:
            print(f"[DEBUG] TeamSelect 缺少参数, 直接使用当前配队")
            return True
        param = int(param.strip("'").strip('"'))
        print( f"[DEBUG] TeamSelect 收到参数: {param}")
        click_box = [0, 0, 100, 45]
        found = False
        max_attempts = 10  # 最多尝试 10 次，防止死循环
        attempt = 0
        
        context.run_task(
            "UtilsOCR",
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "type": "OCR",
                        "param": {
                            "expected": [
                                "选择",
                                "队伍"
                            ],
                            "roi": [
                                51,
                                1,
                                483,
                                94
                            ]
                        }
                    },
                    "action": {
                        "type": "Click",
                    }
                }
            }
        )

        while attempt < max_attempts:
            attempt += 1
            # 每次循环都重新截屏，获取最新图像
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            
            team_list = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi":[55,195,100,470],
                                "expect": "\\d+"
                            }
                        }
                    }
                }
            )

            for team in team_list.filtered_results:
                print(f"[DEBUG] 尝试 {attempt}: 找到团队...")
                print(f"[DEBUG] 团队文本: {team.text}")
                match_num = re.search(r'\d+', team.text)
                print(f"[DEBUG] 提取的数字: {match_num.group() if match_num else '无'}")
                if match_num and int(match_num.group()) == param:
                    found = True
                    click_box[0] = team.box[0] + 1000
                    click_box[1] = team.box[1] + 15
                    break

            if found and click_box[0] != 0 and click_box[1] != 0:
                print(f"[DEBUG] 找到目标团队！点击位置: {click_box}")
                context.run_action(
                    "UtilsClick",
                    click_box,
                    pipeline_override={
                        "UtilsClick": {
                            "action": {             
                                "param": {
                                    "target": click_box
                                }
                            }
                        }
                    }
                )
                print(f"[DEBUG] 已点击目标团队，正在关闭")
                back = context.run_recognition(
                    "UtilsTemplateMatch",
                    current_image,
                    pipeline_override={
                        "UtilsTemplateMatch": {
                            "recognition": {
                                "param": {
                                    "template": "fight/team_exist.png",
                                    "threshold": 0.8,
                                    "roi": [998,4,277,196]
                                }
                            }
                        }
                    }
                )
                if back.best_result:
                    context.run_action(
                        "UtilsClick",
                        back.best_result.box,
                        pipeline_override={
                            "UtilsClick": {
                                "action": {             
                                    "param": {
                                        "target": back.best_result.box
                                    }
                                }
                            }
                        }
                    )
                return True
            
            print(f"[DEBUG] 第 {attempt} 次滑动寻找下一支队伍...")
            context.run_action(
                "UtilsSwipe"
            )
        
        print(f"[DEBUG] 达到最大尝试次数 ({max_attempts})，未找到目标团队")
        return False
