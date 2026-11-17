"""Run the anniversary's available daily quest before claiming rewards.

Event rules: https://housamo.info/zh/news/10th_anniversary/ (section 9).
"""

from datetime import datetime, timezone
import json

import numpy as np
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from utils import info_share, logger


PREFIX = "Reward.SpecialDaily"
LIST_ROI = (494, 3, 779, 671)
MAX_SCROLLS = 12


@AgentServer.custom_action("SpecialDailyReward")
class SpecialDailyReward(CustomAction):
    @staticmethod
    def _task(context, entry):
        result = context.run_task(entry)
        return result is not None and result.status.succeeded and not context.tasker.stopping

    @staticmethod
    def _capture(context):
        if context.tasker.stopping:
            return None
        job = context.tasker.controller.post_screencap().wait()
        if not job.status.succeeded:
            return None
        return context.tasker.controller.cached_image

    @staticmethod
    def _list_image(image):
        x, y, width, height = LIST_ROI
        return image[y:y + height, x:x + width].astype(np.int16)

    @staticmethod
    def _unchanged(previous, current):
        return previous is not None and np.mean(np.abs(previous - current)) < 1.0

    def _find_quest(self, context):
        # Visit the list from its top. Two stationary swipes also tolerate a tap
        # consumed by a transition; the page limit bounds every list traversal.
        for direction in ("Top", "Down"):
            previous = None
            stationary = 0
            for _ in range(MAX_SCROLLS):
                image = self._capture(context)
                if image is None:
                    raise RuntimeError("活动列表截图失败")
                result = context.run_recognition(PREFIX + ".Search", image)
                if result is None:
                    raise RuntimeError("活动列表识别失败")
                if result.hit:
                    return [result.box[i] for i in range(4)]
                current = self._list_image(image)
                stationary = stationary + 1 if self._unchanged(previous, current) else 0
                if stationary >= 2:
                    break
                previous = current
                if not self._task(context, PREFIX + ".Scroll" + direction):
                    raise RuntimeError("活动列表滚动失败")
        return None

    @staticmethod
    def _combat_overrides():
        # These changes live only in a cloned context. Bypass the farming
        # counter, formation scripts and re-entry routes for this one battle.
        return {
            "Activity.Go": {"next": [], "on_error": []},
            "Global.AutoCombat.Start": {"next": ["Global.AutoCombat"]},
            "Global.AutoCombat": {
                "action": {"param": {"custom_action_param": ""}},
                "next": [PREFIX + ".Settle"],
                "on_error": [],
            },
            "Global.AutoCombat.Back1": {"next": [PREFIX + ".Done"], "on_error": []},
            "Global.AutoCombat.BacktoEntry": {"next": [PREFIX + ".Done"], "on_error": []},
        }

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        if context.tasker.stopping:
            return False
        try:
            param = json.loads(argv.custom_action_param)
            now = datetime.now(timezone.utc)
            start = datetime.fromisoformat(param["starts_at"])
            end = datetime.fromisoformat(param["ends_at"])
            if not start <= now < end:
                logger.info("周年每日特别活动未开放，继续领取奖励")
                return True

            scoped = context.clone()
            if not scoped.override_pipeline(self._combat_overrides()):
                return False
            if not self._task(scoped, "Global.Entry"):
                return False
            if not self._task(scoped, "Activity.Go"):
                logger.warning("未进入活动地域，继续领取奖励")
                return self._task(scoped, "Global.Entry")
            try:
                box = self._find_quest(scoped)
            except RuntimeError as error:
                logger.warning(str(error))
                return self._task(scoped, "Global.Entry")
            if box is None:
                logger.info("活动列表未发现可挑战的周年每日关卡，继续领取奖励")
                return self._task(scoped, "Global.Entry")

            clicked = scoped.run_action(
                "UtilsClick", box=box,
                pipeline_override={"UtilsClick": {"action": {"param": {"target": box}}}},
            )
            if clicked is None or not clicked.success or scoped.tasker.stopping:
                return False
            logger.info("发现周年每日关卡，使用当前队伍和游戏 AUTO 挑战一次")
            # Recheck the game's actual AUTO setting, including when a previous
            # task used a different combat script.
            info_share.combat_set = False
            info_share.auto_combat_mode = False
            try:
                battle = scoped.run_task(PREFIX + ".BattleEntry")
            finally:
                info_share.combat_set = False
                info_share.auto_combat_mode = False
                info_share.leader_pos = []
            if scoped.tasker.stopping:
                return False
            nodes = battle.nodes if battle is not None else []
            completed = {node.name for node in nodes if node is not None and node.completed}
            settled = PREFIX + ".Done" in completed and battle.status.succeeded
            if not settled and "Global.AutoCombat.Start" in completed:
                logger.error("周年每日关卡未完成结算")
                return False
            elif not settled and PREFIX + ".NoStamina" in completed:
                logger.warning("周年每日关卡需要 10 点体力，本次未补足体力，继续领取奖励")
            elif not settled:
                logger.warning("周年每日关卡当前未能进入战斗，继续领取奖励")
            returned = self._task(scoped, "Global.Entry")
            if settled and returned:
                logger.info("周年每日关卡已完成并结算，继续领取奖励")
            return returned
        except Exception:
            logger.exception("周年每日关卡检查失败")
            return False
