from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import random
import json
from utils import timeout_mgr, match_mgr, act_mgr, data_io, proj_path, info_share


@AgentServer.custom_action("CombatDrink")
class CombatDrink(CustomAction):
    def __init__(self):
        super().__init__()
        self.all_res = {}
        self.last_fingerprint = []
        self.DATA_PATH = proj_path.AUTO_COMBAT_DIR
        self.IGNORE_LIST = info_share.IGNORE_LIST
        self.DRINK_ITEMS = {"All": "apRecoveryAll.png", 
                            "Half": "apRecoveryHalf.png", 
                            "Mini": "apRecoveryMini.png"
                            }
        self.drink_times = info_share.drink_times.copy()

    def drink(self, context, item, drink_limit, markers):
        if drink_limit.get(item, 0) > self.drink_times[item]:
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            if item != "Ranpoil":
                itemin = context.run_recognition(
                    "UtilsTemplateMatch",
                    current_image,
                    pipeline_override={
                        "UtilsTemplateMatch": {
                            "recognition": {
                                "param": {
                                    "roi": [282,125,789,465],
                                    "template": f"fight/recovery/{self.DRINK_ITEMS[item]}",
                                    "threshold": 0.8,
                                    "order_by": "Score"
                                }
                            }
                        }
                    }
                )
            else:
                itemin = context.run_recognition(
                    "UtilsOCR",
                    current_image,
                    pipeline_override={
                        "UtilsOCR": {
                            "recognition": {
                                "param": {
                                    "roi": [328,172,622,84],
                                    "text": "DP",
                                    "order_by": "Expected"
                                }
                            }
                        }
                    }
                )
            if itemin.best_result:
                context.run_action(
                    "UtilsClick",
                    itemin.best_result.box,
                    pipeline_override={
                        "UtilsClick": {
                            "action":{
                                "type": "Click",
                                "param": {
                                    "target": itemin.best_result.box
                                }
                            }
                        }
                    }
                )
            else:
                print(f"[DEBUG] 屏幕上未找到 {item}")
                return False
            print(f"[DEBUG] 尝试使用 {item}")
        
            drink_scuccess = False
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            insure_res = context.run_recognition(
                "UtilsOCR", 
                current_image,
                pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "post_wait_freezes": {
                            "time": 1000,
                            "target": [1162,610,115,107],
                            "threshold": 0.999
                        },
                        "param": {
                            "roi": [282,348,716,354],
                            "text": markers[0]
                        }
                    }
                }
            })
            if insure_res.best_result:
                if insure_res.best_result.text in markers:
                    context.run_action(
                        "UtilsClick",
                        insure_res.best_result.box,
                        pipeline_override={
                            "UtilsClick": {
                                "action":{
                                    "type": "Click",
                                    "param": {
                                        "target": insure_res.best_result.box
                                    }
                                }
                            }
                        }
                    )
                    drink_scuccess = True
                else:
                    drink_scuccess = False
            if drink_scuccess:
                print(f"[DEBUG] {item} 使用成功")
                context.run_task(
                    "UtilsOCR",
                    pipeline_override={
                        "UtilsOCR": {
                            "recognition": {
                                "pre_wait_freezes": {
                                    "time": 1000,
                                    "target": [302,139,678,444],
                                    "threshold": 0.999
                                },
                                "param": {
                                    "roi": [282,348,716,354],
                                    "text": markers[0]
                                }
                            },
                            "action":{
                                "type": "Click"
                            }
                        }
                    }
                )
                self.drink_times[item] += 1
                return True
            else:
                print(f"[DEBUG] 未找到可用的 {item}")
                return False
        else:
            print(f"[DEBUG] {item} 已达到使用上限")
            return False

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):
            return False
        
        drink_limit = json.loads(argv.custom_action_param)
        print(f"[DEBUG] 药剂使用上限: {drink_limit}")

        match act_mgr.detect_lang(context, [286,298,779,295], ignore=self.IGNORE_LIST):
            case "jp":
                markers = ["OK", "戻る"]
            case "cn":
                markers = ["确定", "返回"]
            case "tw":
                markers = ["OK", "返回"]
            case "en":
                markers = ["OK", "Back"]

        if self.drink(context, "All", drink_limit, markers):
            info_share.drink_times["All"] = self.drink_times["All"]
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        elif self.drink(context, "Half", drink_limit, markers):
            info_share.drink_times["Half"] = self.drink_times["Half"]
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        elif self.drink(context, "Mini", drink_limit, markers):
            info_share.drink_times["Mini"] = self.drink_times["Mini"]
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        elif self.drink(context, "Ranpoil", drink_limit, markers):
            info_share.drink_times["Ranpoil"] = self.drink_times["Ranpoil"]
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        else:
            print(f"[DEBUG] 未找到可用的补给道具")
            context.run_task(
                "UtilsOCR",
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": [0,0,175,133],
                                "text": markers[1]
                            }
                        },
                        "action":{
                            "type": "Click"
                        }
                    }
                }
            )
            return False

            
        
        # match act_mgr.detect_lang(context, [192,81,895,546], ignore=self.IGNORE_LIST):
        #     case "jp":
        #         markers = ["クエスト画面", "再突入", "所持", "再突入", "キャンセル"]
        #     case "cn":
        #         markers = ["再次挑战", "回任务画面", "持有", "再次挑战", "取消"]
        #     case "tw":
        #         markers = ["再次挑戰", "回任務畫面", "持有", "再次挑戰", "取消"]
        #     case "en":
        #         markers = ["Play Again", "Return to Quests", "Possess", "Play Again", "Cancel"]