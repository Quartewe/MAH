from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import random
import json
import time
from utils import logger, timeout_mgr, match_mgr, act_mgr, data_io, proj_path, info_share


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

    def _record_use(self, item):
        self.drink_times[item] += 1
        info_share.drink_times[item] = self.drink_times[item]

    @staticmethod
    def _click(context, box):
        result = context.run_action(
            "UtilsClick", box,
            pipeline_override={"UtilsClick": {"action": {"param": {"target": box}}}},
        )
        return result is not None and result.success

    @staticmethod
    def _ocr(context, image, roi, text):
        return context.run_recognition(
            "UtilsOCR", image,
            pipeline_override={"UtilsOCR": {"recognition": {"param": {
                "roi": roi, "text": text
            }}}},
        )

    def _dp_transition_seen(self, context, image):
        # 只凭确认文字消失无法确认恢复：DP 提示也必须消失，且已进入后续画面。
        prompt = self._ocr(context, image, [328, 172, 622, 84], "DP")
        if prompt is None or prompt.best_result:
            return False
        loading = self._ocr(context, image, [9, 572, 522, 148], "LOADING")
        if loading is not None and loading.best_result:
            return True
        battle = self._ocr(context, image, [0, 0, 640, 66], "MENU")
        if battle is not None and battle.best_result:
            return True
        support = context.run_recognition(
            "UtilsTemplateMatch", image,
            pipeline_override={"UtilsTemplateMatch": {"recognition": {"param": {
                "template": "fight/support/support_default.png", "roi": [110, 93, 799, 72]
            }}}},
        )
        return support is not None and bool(support.best_result)

    def drink(self, context, item, drink_limit, markers):
        if drink_limit.get(item, 0) <= self.drink_times[item]:
            logger.info(f"{item} 已达到使用上限")
            return False
        context.tasker.controller.post_screencap().wait()
        image = context.tasker.controller.cached_image
        if item == "Ranpoil":
            itemin = self._ocr(context, image, [328, 172, 622, 84], "DP")
        else:
            itemin = context.run_recognition(
                "UtilsTemplateMatch", image,
                pipeline_override={"UtilsTemplateMatch": {"recognition": {"param": {
                    "roi": [282, 125, 789, 465],
                    "template": f"fight/recovery/{self.DRINK_ITEMS[item]}",
                    "threshold": 0.8, "order_by": "Score"
                }}}},
            )
        if itemin is None or not itemin.best_result:
            return False
        if not self._click(context, itemin.best_result.box):
            return False

        # DP 的入口点击可能直接消耗药剂；请求已发出即占用额度，后续无法确认
        # 成功时也不能再次发出同一次额度的请求。AP 在确认消耗时记账。
        if item == "Ranpoil":
            self._record_use(item)
        transition_hits = 0
        for _ in range(10):
            if context.tasker.stopping:
                return False
            context.tasker.controller.post_screencap().wait()
            image = context.tasker.controller.cached_image
            confirm = self._ocr(context, image, [282, 348, 716, 354], markers[0])
            if confirm is not None and confirm.best_result and confirm.best_result.text in markers:
                if not self._click(context, confirm.best_result.box):
                    return False
                if item != "Ranpoil":
                    self._record_use(item)
                acknowledgement = context.run_task(
                    "UtilsOCR",
                    pipeline_override={"UtilsOCR": {
                        "recognition": {"param": {"roi": [282, 348, 716, 354], "text": markers[0]}},
                        "action": {"type": "Click"}
                    }},
                )
                if not act_mgr.task_succeeded(acknowledgement):
                    logger.error(f"{item} 已提交使用请求，但恢复结果未确认")
                    return False
                logger.info(f"{item} 使用成功")
                return True
            if item == "Ranpoil":
                transition_hits = transition_hits + 1 if self._dp_transition_seen(context, image) else 0
                if transition_hits >= 2:
                    logger.info("DP 补给后已进入后续画面")
                    return True
            time.sleep(0.5)
        logger.error(f"未能确认 {item} 恢复成功")
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
        logger.info(f"药剂使用上限: {drink_limit}")

        # 包含弹窗标题和返回按钮，不能只用道具数量所在的区域判断语言。
        match act_mgr.detect_lang(context, [0,0,1070,595], ignore=self.IGNORE_LIST):
            case "jp":
                markers = ["OK", "戻る"]
            case "cn":
                markers = ["确定", "返回"]
            case "tw":
                markers = ["OK", "返回"]
            case "en":
                markers = ["OK", "Back"]
            case _:
                logger.error("无法确定补给界面语言")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False

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
            logger.info(f"未找到可用的补给道具")
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
            timeout_mgr.stop_monitoring(argv.node_name)
            return False
