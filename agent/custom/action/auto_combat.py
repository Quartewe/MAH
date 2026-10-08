from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils import logger, timeout_mgr, data_io, act_mgr, match_mgr, proj_path, info_share
import random
import time

# TODO: 修复无法识别skill的问题

@AgentServer.custom_action("AutoCombat")
class AutoCombat(CustomAction):
    def __init__(self):
        super().__init__()
        self.toolbar_roi = [0, 0, 640, 66]
        self.fight_roi = [643, 0, 636, 719]
        self.DATA_PATH = proj_path.AUTO_COMBAT_DIR
        self.detect_complete_error = False
        self.if_complete = False
        self.UNIT_LENGTH = 110
        
    def _move_data(self, action_list, start_pos=None):
        if start_pos is None:
            start_pos = [0, 0]

        end_points = []
        current_pos = [start_pos[0], start_pos[1]]

        for action in action_list:
            if action == "U":
                current_pos = [current_pos[0], current_pos[1] - self.UNIT_LENGTH]
            if action == "D":
                current_pos = [current_pos[0], current_pos[1] + self.UNIT_LENGTH]
            if action == "L":
                current_pos = [current_pos[0] - self.UNIT_LENGTH, current_pos[1]]
            if action == "R":
                current_pos = [current_pos[0] + self.UNIT_LENGTH, current_pos[1]]
            if action == "S":
                a = random.randint(-30, 30)
                b = random.randint(-30, 30)
                while (a ** 2 + b ** 2) < 1250 or (a ** 2 + b ** 2) > 1300 or abs(a) - abs(b) > 10:
                    a = random.randint(-30, 30)
                    b = random.randint(-30, 30)
                current_pos = [
                    current_pos[0] + a,
                    current_pos[1] + b,
                ]
            end_points.append([current_pos[0] - 8, current_pos[1] - 8, 15, 15] if action != "S" else [current_pos[0], current_pos[1]])

        return end_points

    def _get_posL(self, context):
        i = 0
        while i < 30:
            if self._check_running(context):
                return None
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            leader = context.run_recognition(
                "UtilsTemplateMatch",
                current_image,
                pipeline_override={
                    "UtilsTemplateMatch": {
                        "pre_wait_freezes":{
                            "time": 1500,
                            "target": [647,373,583,342],
                            "threshold": 0.99,
                            "timeout": 15000,
                        },
                        "recognition": {
                            "param": {
                                "roi": [647,373,583,342],
                                "threshold": 0.8,
                                "template": "fight/L.png",
                            }
                        }
                    }
                },
            )
            logger.info(f"原始ocr输出: {leader.all_results}")
            if leader.best_result:
                logger.info(f"检测到队长位置: {leader.best_result.box}")
                return [leader.best_result.box[0] + 38, leader.best_result.box[1] - 5]
            logger.info("未检测到队长位置，正在重试...")
            time.sleep(1)
            i += 1
        return None

    def _get_all_pos(self, pos_data: dict, last_move):
        current_pos = {}
        for char_key, pos in pos_data.items():
            if isinstance(pos, list) and len(pos) >= 2:
                current_pos[str(char_key)] = [pos[0], pos[1]]
            else:
                current_pos[str(char_key)] = pos

        if not last_move:
            return current_pos

        moved_char = None
        action_list = []
        if isinstance(last_move, dict):
            moved_char = str(last_move.get("char"))
            action_list = last_move.get("action", [])
        elif isinstance(last_move, list):
            action_list = last_move

        if moved_char is None or moved_char not in current_pos:
            return current_pos

        moved_pos = current_pos[moved_char]
        if not isinstance(moved_pos, list) or len(moved_pos) < 2:
            return current_pos

        for move in action_list:
            old_pos = [moved_pos[0], moved_pos[1]]
            next_pos = [moved_pos[0], moved_pos[1]]

            match move:
                case "U":
                    next_pos = [moved_pos[0], moved_pos[1] - 1]
                case "D":
                    next_pos = [moved_pos[0], moved_pos[1] + 1]
                case "L":
                    next_pos = [moved_pos[0] - 1, moved_pos[1]]
                case "R":
                    next_pos = [moved_pos[0] + 1, moved_pos[1]]
                case "S":
                    next_pos = moved_pos

            if next_pos != old_pos:
                overlap_char = None
                for char_key, char_pos in current_pos.items():
                    if char_key == moved_char:
                        continue
                    if not isinstance(char_pos, list) or len(char_pos) < 2:
                        continue
                    if char_pos[0] == next_pos[0] and char_pos[1] == next_pos[1]:
                        overlap_char = char_key
                        break

                if overlap_char is not None:
                    current_pos[overlap_char] = old_pos

            moved_pos = next_pos

        current_pos[moved_char] = moved_pos
        return current_pos

    def _get_abs_pos(self, posL, char_pos_relative, pos_data):
        if (
            not isinstance(posL, list)
            or len(posL) < 2
            or not isinstance(char_pos_relative, list)
            or len(char_pos_relative) < 2
        ):
            print(
                f"[WARNING] 位置数据无效: posL={posL}, char_pos_relative={char_pos_relative}, pos_data={pos_data}"
            )
            return None

        return [
            posL[0] + char_pos_relative[0] * self.UNIT_LENGTH,
            posL[1] + char_pos_relative[1] * self.UNIT_LENGTH,
            15,
            15,
        ]

    def _check_running(self, context):
        """轻量检查：仅检测任务是否被用户终止，不执行任何识别"""
        if context.tasker.stopping:
            logger.info("检测到用户终止任务，正在退出...")
            self.if_complete = True
            return True
        return False

    def _detect_complete(self, context):
        """检测战斗是否结束，若结束则设置 self.if_complete = True"""
        if self.if_complete or self.detect_complete_error:
            return True
        if self._check_running(context):
            return True
        try:
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            complete_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "pre_wait_freezes":{
                            "time": 500,
                            "target": [649,25,629,693],
                            "threshold": 0.99,
                            "timeout": 15000,
                        },
                        "recognition": {
                            "param": {
                                "roi": [424,635,426,61],
                                "expected": ["TOUCHSCREEN", "TOUCH", "SCREEN", "TOUCH SCREEN"],
                                "order_by": "Expected"
                            }
                        }
                    }
                },
            )
            back_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": [1027,490,221,200],
                                "expected": ["再突入", "再次挑战", "Play Again", "再次挑戰"],
                                "order_by": "Expected",
                            }
                        }
                    }
                },
            )
            logger.info(f"_detect_complete: TOUCH SCREEN识别结果: {complete_res.all_results}")
            logger.info(f"_detect_complete: 返回按钮识别结果: {back_res.all_results}")
            if self._check_running(context):
                return True

            if complete_res.best_result:
                logger.info(f"检测到战斗结束文本: {complete_res.best_result.text}，正在点击继续...")
                context.run_action(
                    "UtilsClick",
                    box=complete_res.best_result.box,
                    pipeline_override={
                        "UtilsClick": {
                            "action": {
                                "param": {
                                    "target": complete_res.best_result.box,
                                }
                            }
                        }
                    },
                )
                self.if_complete = True
                return True
            elif back_res.best_result:
                logger.info(f"检测到返回按钮文本: {back_res.best_result.text}，正在点击继续...")
                self.if_complete = True
                return True
            else:
                logger.info("_detect_complete: OCR未检测到结果")
            return False
        except Exception as e:
            logger.error(f"_detect_complete 异常: {e}")
            import traceback
            self.detect_complete_error = True
            traceback.print_exc()
            return True

    def _wait_for_complete(self, context, max_wait=300):
        """脚本动作已执行完时，只等待结算，不重新定位或重放动作。"""
        start = time.monotonic()
        while not self.if_complete:
            self._detect_complete(context)
            if self.detect_complete_error or context.tasker.stopping:
                return False
            if self.if_complete:
                return True
            if time.monotonic() - start >= max_wait:
                logger.warning(f"脚本动作已结束，等待结算 {max_wait} 秒后超时")
                return False
            time.sleep(1)
        return not self.detect_complete_error and not context.tasker.stopping

    def _combat(
        self,
        context,
        action_data,
        posL,
        pos_data
    ):
        current_pos_data = {
            str(char_key): [pos[0], pos[1]] if isinstance(pos, list) and len(pos) >= 2 else pos
            for char_key, pos in pos_data.items()
        }

        for i in range(len(action_data)):
            if self._detect_complete(context):
                logger.info("检测到战斗结束，正在退出...")
                return current_pos_data

            # init
            action = action_data.get(f"{i}", None)
            if not action:
                break
            action_char = action["char"]
            action_list = action["action"]
            char_pos_relative = current_pos_data.get(f"{action_char}", None)
            char_pos = self._get_abs_pos(posL, char_pos_relative, current_pos_data)
            end_points = self._move_data(action_list, char_pos)

            # action
            logger.info(
                f"[DEBUG] 动作 {i}: 角色 {action_char}, 位置 {char_pos}, 动作序列 {action_list}, 行动后坐标列表 {end_points}"
            ) 

            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            detect_skill = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "pre_wait_freezes": {
                            "time": 1000,
                            "target": [1162,610,115,107],
                            "threshold": 0.999
                        },
                        "recognition": {
                            "param": {
                                "roi": [649,25,629,693],
                                "expected": "SKILL",
                            }
                        }
                    }
                }
            )

            logger.info(f"动作 {i} 即将执行滑动...")
            logger.info(f"技能状态检测结果: {detect_skill.filtered_results}")
            if detect_skill.best_result:
                logger.info(f"存在单位的技能被禁用, 尝试忽略等待, 位置为:{detect_skill.best_result}")
            else:
                logger.info(f"未检测到技能状态，默认执行滑动并等待...")

            # 重操作前检查：若用户已取消则跳过滑动
            if self._check_running(context):
                return current_pos_data

            context.run_action(
                "UtilsSwipe",
                pipeline_override={
                    "UtilsSwipe": {
                        "pre_wait_freezes":{
                            "time": 1000 if not detect_skill.best_result else 0,
                            "target": [649,25,629,693],
                            "threshold": 0.999,
                            "timeout": 15000,
                        },
                        "post_wait_freezes":{
                            "time": 1000 if not detect_skill.best_result else 0,
                            "target": [649,25,629,693],
                            "threshold": 0.999,
                            "timeout": 15000,
                        },
                        "begin": char_pos,
                        "end": end_points,
                        "duration": 100,
                        "end_hold": 0
                    }
                },
            )

            logger.info(f"动作 {i} 已执行，等待回合变化...")

            # 重操作后检查：滑动期间用户可能已取消
            if self._check_running(context):
                return current_pos_data

            if self._detect_complete(context):
                logger.info("检测到战斗结束，正在退出...")
                return current_pos_data

            current_pos_data = self._get_all_pos(current_pos_data, action)
            logger.info(f"动作 {i} 后更新相对位置: {current_pos_data}")

        return current_pos_data


    def _enable_options(self, context, node_name):
        """确认菜单、设置内容和返回战斗三个状态，不把点击成功当成页面已切换。"""
        deadline = time.monotonic() + 45
        closing = False
        clicked_options = set()

        def running():
            return (not context.tasker.stopping
                    and time.monotonic() < deadline
                    and not timeout_mgr.check_timeout(node_name))

        def recognize(image, roi, expected):
            result = context.run_recognition(
                "UtilsOCR", image,
                pipeline_override={"UtilsOCR": {"recognition": {"param": {
                    "roi": roi, "expected": expected,
                }}}},
            )
            return result.filtered_results if result is not None else None

        def click(box):
            if not running():
                return False
            result = context.run_action(
                "UtilsClick", box=box,
                pipeline_override={"UtilsClick": {
                    "pre_wait_freezes": 0,
                    "action": {"param": {"target": box}},
                }},
            )
            return result is not None and result.success

        while running():
            if not context.tasker.controller.post_screencap().wait().succeeded:
                logger.error("战斗菜单截图失败")
                return False
            image = context.tasker.controller.cached_image
            # 两个控件须在同一帧出现；战斗背景的 MENU 文字始终可能可见。
            settings = recognize(image, [500, 70, 220, 65], ["^设定$", "^設定$", "^Settings$"])
            back = recognize(image, [1050, 85, 190, 65], ["^返回$", "^戻る$", "^Back$"])
            if settings is None or back is None:
                logger.error("战斗菜单识别失败")
                return False

            if settings and back:
                if closing:
                    if not click(back[0].box):
                        return False
                else:
                    switches = recognize(image, [170, 210, 70, 300], ["^ON$", "^OFF$"])
                    if switches is None:
                        logger.error("战斗设置选项识别失败")
                        return False
                    switches = sorted(switches, key=lambda result: result.box[1])
                    # 每一行各有一个开关，排除漏识别以及单行重复 OCR 框。
                    complete = len(switches) == 3 and all(
                        top <= result.box[1] < bottom
                        for result, (top, bottom) in zip(switches, [(210, 310), (310, 425), (425, 510)])
                    )
                    if complete:
                        off = [(i, result) for i, result in enumerate(switches) if result.text.strip() == "OFF"]
                        if not off:
                            logger.info("已确认战斗设置三项均为 ON，正在返回战斗")
                            closing = True
                            if not click(back[0].box):
                                return False
                        else:
                            for i, result in off:
                                # 点击后等待新的 ON 结果，避免旧帧导致重复点击把开关关回去。
                                if i not in clicked_options:
                                    if not click(result.box):
                                        return False
                                    clicked_options.add(i)
                                    break
                    elif not switches:
                        # MENU 会记住上次的页签；只有尚无设置内容时才切换页签。
                        if not click(settings[0].box):
                            return False
            elif not settings and not back:
                menu = recognize(image, self.toolbar_roi, ["^MENU$"])
                if menu is None:
                    return False
                if menu:
                    if closing:
                        logger.info("已确认返回战斗画面")
                        return running()
                    if not click(menu[0].box):
                        return False
            # 战斗动画期间点击可能被忽略；先等新画面，再决定是否重试。
            time.sleep(0.5)

        if context.tasker.stopping:
            logger.info("战斗设置初始化已取消")
        else:
            logger.error("等待战斗菜单或设置状态超时")
        return False

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 每次调用覆盖一整局；不能拿上一局的队长位置校正本局棋盘。
        info_share.leader_pos = []
        if timeout_mgr.check_timeout(argv.node_name):
            return False

        def ensure_speed_4x():
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            speed_res = context.run_recognition(
                "UtilsTemplateMatch",
                current_image,
                pipeline_override={
                    "UtilsTemplateMatch": {
                        "recognition": {
                            "pre_wait_freezes":{
                                "time": 500,
                                "target": [647,373,583,342],
                                "threshold": 0.99,
                                "timeout": 15000,
                            }, 
                            "param": {
                                "roi": self.toolbar_roi,
                                "threshold": 0.95,
                                "template": "fight/speed.png",
                            }
                        }
                    }
                },
            )
            if speed_res.best_result:
                speed = len(speed_res.filtered_results)
                logger.info(f"当前速度: {speed}x，需要切换次数: {4 - speed}")
                for _ in range(4 - speed):
                    context.run_action(
                        "UtilsClick",
                        box=speed_res.best_result.box,
                        pipeline_override={
                            "UtilsClick": {
                                "action": {
                                    "param": {
                                        "target": speed_res.best_result.box,
                                    }
                                }
                            }
                        },
                    )
            else:
                logger.info("速度已是 4x")

        def auto_combat() -> bool:
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            auto_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "pre_wait_freezes": 0,
                            "param": {
                                "roi": self.toolbar_roi,
                                "expected": "OFF",
                            }
                        }
                    }
                },
            )
            if auto_res.best_result:
                context.run_action(
                    "UtilsClick",
                    pipeline_override={
                        "UtilsClick": {
                            "pre_wait_freezes":{
                                "time": 500,
                                "target": [647,373,583,342],
                                "threshold": 0.99,
                                "timeout": 15000,
                            },
                            "action": {
                                "param": {
                                    "target": auto_res.best_result.box,
                                }
                            }
                        }
                    },
                )
                info_share.auto_combat_mode = True
                logger.info("已开启自动战斗模式")
                return True
            else:
                on_res = context.run_recognition(
                    "UtilsOCR",
                    current_image,
                    pipeline_override={
                        "UtilsOCR": {
                            "recognition": {
                                "pre_wait_freezes": 0,
                                "param": {
                                    "roi": self.toolbar_roi,
                                    "expected": "ON",
                                }
                            }
                        }
                    },
                )
                if on_res.best_result:
                    info_share.auto_combat_mode = True
                    logger.info("自动战斗模式已开启")
                    return True

                info_share.auto_combat_mode = False
                logger.warning("无法识别自动战斗开关状态")
                return False

        def disable_auto_combat():
            result = context.run_task(
                "UtilsOCR",
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": self.toolbar_roi,
                                "expected": "ON",
                            }
                        },
                        "action": {"type": "click"},
                    }
                },
            )
            if not act_mgr.task_succeeded(result):
                return False
            logger.info("已关闭自动战斗模式")
            info_share.auto_combat_mode = False
            return True

        def analyze_data(action_data):
            if not isinstance(action_data, dict):
                logger.warning(f"动作数据类型无效: {type(action_data)}")
                return {}, {}

            def normalize_actions(raw_actions):
                if not isinstance(raw_actions, dict):
                    return {}

                valid_items = []
                for key, value in raw_actions.items():
                    if str(key).isdigit() and isinstance(value, dict):
                        valid_items.append((int(key), value))

                valid_items.sort(key=lambda item: item[0])
                return {str(index): item[1] for index, item in enumerate(valid_items)}

            base_action_data = normalize_actions(action_data)
            loop_action_data = normalize_actions(action_data.get("loop", {}))

            print(
                f"[DEBUG] 动作数据解析完成: 基础动作 {len(base_action_data)} 条, 循环动作 {len(loop_action_data)} 条"
            )
            return base_action_data, loop_action_data

        def list_combat(pos_data, base_action_data, posL):
            if not base_action_data:
                logger.warning("未配置基础战斗动作")
                return pos_data

            current_pos_data = self._combat(
                context,
                base_action_data,
                posL,
                pos_data
            )

            return current_pos_data

        def loop_combat(current_pos_data, loop_action_data, posL):
            if not loop_action_data:
                logger.warning("循环动作为空")
                return False, current_pos_data

            logger.info("已启用循环战斗，开始循环执行动作")
            start = time.monotonic()
            max_wait = 300
            loop_count = 0

            while not self.if_complete:
                if self._detect_complete(context):
                    logger.info("循环阶段检测到战斗结束，正在退出...")
                    break
                
                if self.detect_complete_error:
                    logger.warning("检测到 _detect_complete 之前出现错误，为避免潜在死循环，退出循环战斗")
                    return False, current_pos_data

                loop_count += 1
                if self._check_running(context):
                    return False, current_pos_data
                current_pos_data = self._combat(
                    context,
                    loop_action_data,
                    posL,
                    current_pos_data
                )

                if self.if_complete:
                    break

                if time.monotonic() - start > max_wait:
                    logger.warning(f"循环战斗等待 {max_wait} 秒后超时")
                    return False, current_pos_data

                logger.info(f"循环战斗第 {loop_count} 轮未完成，正在重试...")

            logger.info("循环战斗已完成，正在退出...")
            return self.if_complete and not self.detect_complete_error and not context.tasker.stopping, current_pos_data

        def main() -> bool:
            param = argv.custom_action_param
            if isinstance(param, str):
                param = param.strip('"').strip()

            raw_data = None

            if param:
                raw_data = data_io.find_target_files(self.DATA_PATH, param)
            else:
                auto_mode = True
            fight_data = raw_data.get("fight", {}) if raw_data else {}
            pos_data = fight_data.get("pos", {})
            action_data = fight_data.get("action", {})
            auto_mode = not fight_data

            if not info_share.combat_set and not info_share.auto_combat_mode:
                if not self._enable_options(context, argv.node_name):
                    return False
                ensure_speed_4x()
                info_share.combat_set = True

            elif not info_share.combat_set and info_share.auto_combat_mode:
                if not disable_auto_combat() or not self._enable_options(context, argv.node_name):
                    return False
                ensure_speed_4x()
                info_share.combat_set = True

            if auto_mode:
                if not info_share.auto_combat_mode:
                    if not auto_combat():
                        logger.error("开启或校验自动战斗模式失败")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return False

                start = time.monotonic()
                max_wait = 180
                while not self.if_complete:
                    logger.info("自动战斗模式运行中，等待战斗结束...")
                    self._detect_complete(context)
                    if self.detect_complete_error:
                        return False
                    if self._check_running(context):
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return False
                    if time.monotonic() - start > max_wait:
                        logger.warning(f"自动战斗等待 {max_wait} 秒后超时")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return False
                    time.sleep(1)

                logger.info("自动战斗已完成")
                timeout_mgr.stop_monitoring(argv.node_name)
                return True

            if info_share.auto_combat_mode:
                if not disable_auto_combat():
                    return False

            if not info_share.auto_combat_mode:
                battle_origin = self._get_posL(context)
                if not battle_origin:
                    logger.error("无法通过开局队长位置确定棋盘基准，停止本局作战")
                    return False
                # 基准固定到本局退出；之后只更新角色的相对格子位置。
                # leader 移动或退场都不触发再次识别或基准修正。
                info_share.leader_pos = battle_origin.copy()
                logger.info(f"本局棋盘基准已固定: {battle_origin}")
                base_action_data, loop_action_data = analyze_data(action_data)
                current_pos_data = list_combat(pos_data, base_action_data, battle_origin)
                if self.detect_complete_error or context.tasker.stopping:
                    return False
                if loop_action_data and not self.if_complete:
                    logger.info("基础执行完成，开始循环战斗...")
                    loop_completed, _ = loop_combat(current_pos_data, loop_action_data, battle_origin)
                    if loop_completed:
                        logger.info("循环战斗已完成")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return True
                    else: 
                        logger.warning("循环战斗未完成，将按当前进度退出")
                    timeout_mgr.stop_monitoring(argv.node_name)
                    return False
                else:
                    logger.info("脚本动作已执行完，等待本局结算")
                    return self._wait_for_complete(context)
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        try:
            result = main()
            return result and not self.detect_complete_error and not context.tasker.stopping
        finally:
            info_share.leader_pos = []
            self.detect_complete_error = False
            self.if_complete = False
            timeout_mgr.stop_monitoring(argv.node_name)
