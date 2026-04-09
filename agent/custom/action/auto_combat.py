from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils import timeout_mgr, data_io, act_mgr, match_mgr, proj_path, info_share
import random
import time

@AgentServer.custom_action("AutoCombat")
class AutoCombat(CustomAction):
    def __init__(self):
        super().__init__()
        self.toolbar_roi = [0, 0, 640, 66]
        self.fight_roi = [643, 0, 636, 719]
        self.DATA_PATH = proj_path.AUTO_COMBAT_DIR
        self.detect_complete_error = False
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
                            "timeout": -1,
                        },
                        "recognition": {
                            "param": {
                                "roi": self.fight_roi,
                                "threshold": 0.9,
                                "template": "fight/L.png",
                            }
                        }
                    }
                },
            )
            if leader.best_result:
                print(f"[DEBUG] 检测到队长位置: {leader.best_result.box}")
                return [leader.best_result.box[0] + 38, leader.best_result.box[1] - 5]
            print("[DEBUG] 未检测到队长位置，正在重试...")
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

    def _detect_complete(self, context):
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
                            "timeout": -1,
                        },
                        "recognition": {
                            "param": {
                                "roi": [424,635,426,61],
                                "expected": "",
                                "order_by": "Expected"
                            }
                        }
                    }
                },
            )
            print(f"[DEBUG] _detect_complete: OCR识别结果: {complete_res.all_results}")
            if not context.tasker.running:
                print("[DEBUG] 用户终止, 正在退出...")
                self.detect_complete_error = True
                return True
            back_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": [1027,490,221,200],
                                "expected": "",
                                "order_by": "Expected",
                            }
                        }
                    }
                },
            )
            if complete_res.best_result and complete_res.best_result.score > 0.8:
                text = complete_res.best_result.text
                print(f"[DEBUG] _detect_complete: OCR识别结果: {text}")
                if match_mgr.fuzzy_match("TOUCHSCREEN", text):
                    print(f"[DEBUG] 检测到战斗结束文本: {text}，正在点击继续...")
                    context.run_action(
                        "UtilsClick",
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
                    return True
            elif back_res.best_result and back_res.best_result.score > 0.8:
                text = back_res.best_result.text
                print(f"[DEBUG] 检测到战斗结束文本: {text}，正在点击继续...")
                return True
            else:
                print("[DEBUG] _detect_complete: OCR未检测到结果")
            return False
        except Exception as e:
            print(f"[ERROR] _detect_complete 异常: {e}")
            import traceback
            self.detect_complete_error = True
            traceback.print_exc()
            return True
        
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
                print("[DEBUG] 检测到战斗结束，正在退出...")
                return True, current_pos_data

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
            print(
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

            print(f"[DEBUG] 动作 {i} 即将执行滑动...")

            context.run_action(
                "UtilsSwipe",
                pipeline_override={
                    "UtilsSwipe": {
                        "pre_wait_freezes":{
                            "time": 1000 if not detect_skill.best_result else 0,
                            "target": [649,25,629,693],
                            "threshold": 0.999,
                            "timeout": -1,
                        },
                        "post_wait_freezes":{
                            "time": 1000 if not detect_skill.best_result else 0,
                            "target": [649,25,629,693],
                            "threshold": 0.999,
                            "timeout": -1,
                        },
                        "begin": char_pos,
                        "end": end_points,
                        "duration": 100,
                        "end_hold": 0
                    }
                },
            )

            print(f"[DEBUG] 动作 {i} 已执行，等待回合变化...")

            if self._detect_complete(context):
                print("[DEBUG] 检测到战斗结束，正在退出...")
                return True, current_pos_data

            current_pos_data = self._get_all_pos(current_pos_data, action)
            print(f"[DEBUG] 动作 {i} 后更新相对位置: {current_pos_data}")

        return True, current_pos_data


    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        if timeout_mgr.check_timeout(argv.node_name):
            return False

        def get_markers_by_lang():
            lang = act_mgr.detect_lang(context, [74, 70, 640, 51])
            if lang == "cn":
                return ["设定", "返回"]
            if lang == "tw":
                return ["設定", "返回"]
            if lang == "jp":
                return ["設定", "戻る"]
            if lang == "en":
                return ["Settings", "Back"]

            print(f"[WARNING] 未知语言: {lang}，默认使用英文")
            return ["Settings", "Back"]
        
        def enable_options():
            context.run_task(
                "UtilsOCR",
                pipeline_override={
                    "UtilsOCR": {
                        "pre_wait_freezes":{
                            "time": 1500,
                            "target": [647,373,583,342],
                            "threshold": 0.999,
                            "timeout": -1,
                        },
                        "recognition": {
                            "param": {
                                "roi": self.toolbar_roi,
                                "expected": "MENU",
                                "order_by": "Expected",
                            }
                        },
                        "action": {"type": "click"},
                    }
                },
            )
            print("[DEBUG] 已点击菜单...")

            markers = get_markers_by_lang()

            setting = context.run_task(
                "UtilsOCR",
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "expected": markers[0],
                            }
                        },
                        "action": {"type": "click"},
                        "timeout": 0,
                    }
                },
            )
            print(f"[DEBUG] 已点击 {markers[0]}...")
            time.sleep(5)
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            option_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": [78, 140, 844, 422],
                                "expected": "OFF",
                            }
                        }
                    }
                },
            )
            print(f"[DEBUG] 选项识别结果: {option_res.filtered_results}")
            if option_res.best_result:
                for res in option_res.filtered_results:
                    if "OFF" in res.text:
                        print(f"[DEBUG] 已点击 {res.text} 选项...")
                        context.run_action(
                            "UtilsClick",
                            pipeline_override={
                                "UtilsClick": {
                                    "action": {
                                        "param": {
                                            "target": res.box,
                                        }
                                    }
                                }
                            },
                        )
            context.run_task(
                "UtilsOCR",
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": [959, 65, 304, 234],
                                "expected": markers[1],
                            }
                        },
                        "action": {"type": "click"},
                    }
                },
            )

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
                                "timeout": -1,
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
                print(f"[DEBUG] 当前速度: {speed}x，需要切换次数: {4 - speed}")
                for _ in range(4 - speed):
                    context.run_action(
                        "UtilsClick",
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
                print("[DEBUG] 速度已是 4x")

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
                                "timeout": -1,
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
                print("[DEBUG] 已开启自动战斗模式")
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
                    print("[DEBUG] 自动战斗模式已开启")
                    return True

                info_share.auto_combat_mode = False
                print("[WARNING] 无法识别自动战斗开关状态")
                return False

        def disable_auto_combat():
            context.run_task(
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
            print("[DEBUG] 已关闭自动战斗模式")
            info_share.auto_combat_mode = False

        def analyze_data(action_data):
            if not isinstance(action_data, dict):
                print(f"[WARNING] 动作数据类型无效: {type(action_data)}")
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
                print("[WARNING] 未配置基础战斗动作")
                return False, pos_data

            list_complete, current_pos_data = self._combat(
                context,
                base_action_data,
                posL,
                pos_data
            )

            return list_complete, current_pos_data

        def loop_combat(current_pos_data, loop_action_data, posL):
            if not loop_action_data:
                print("[WARNING] 循环动作为空")
                return False, current_pos_data

            print("[DEBUG] 已启用循环战斗，开始循环执行动作")
            start = time.monotonic()
            max_wait = 300
            loop_count = 0

            while True:
                if self._detect_complete(context):
                    print("[DEBUG] 循环阶段检测到战斗结束，正在退出...")
                    return True, current_pos_data
                
                if self.detect_complete_error:
                    print("[WARNING] 检测到 _detect_complete 之前出现错误，为避免潜在死循环，退出循环战斗")
                    return False, current_pos_data

                loop_count += 1
                loop_complete, current_pos_data = self._combat(
                    context,
                    loop_action_data,
                    posL,
                    current_pos_data
                )

                if not loop_complete:
                    return False, current_pos_data
                
                if self._detect_complete(context):
                    print("[DEBUG] 循环阶段检测到战斗结束，正在退出...")
                    return True, current_pos_data

                if time.monotonic() - start > max_wait:
                    print(f"[WARNING] 循环战斗等待 {max_wait} 秒后超时")
                    return False, current_pos_data

                print(f"[DEBUG] 循环战斗第 {loop_count} 轮未完成，正在重试...")

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
                enable_options()
                ensure_speed_4x()
                info_share.combat_set = True

            elif not info_share.combat_set and info_share.auto_combat_mode:
                disable_auto_combat()
                enable_options()
                ensure_speed_4x()
                info_share.combat_set = True

            if auto_mode:
                if not info_share.auto_combat_mode:
                    if not auto_combat():
                        print("[ERROR] 开启或校验自动战斗模式失败")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return False

                start = time.monotonic()
                max_wait = 180
                while True:
                    print("[DEBUG] 自动战斗模式运行中，等待战斗结束...")
                    ifcompleted = self._detect_complete(context)
                    if ifcompleted:
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return True
                    time.sleep(1)  # 减少 CPU 占用，保持响应速度
                    if time.monotonic() - start > max_wait:
                        print(f"[WARNING] 自动战斗等待 {max_wait} 秒后超时")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return False

            if info_share.auto_combat_mode:
                disable_auto_combat()

            if not info_share.auto_combat_mode:
                posL = self._get_posL(context)
                if not info_share.leader_pos:
                    info_share.leader_pos = posL
                elif abs(info_share.leader_pos[0] - posL[0]) > 20 or abs(info_share.leader_pos[1] - posL[1]) > 20:
                    time.sleep(1)
                    print(f"[WARNING] 检测到队长位置变化，正在复核位置准确性...")
                    last_posL = posL
                    current_posL = self._get_posL(context)
                    if abs(last_posL[0] - current_posL[0]) > 20 or abs(last_posL[1] - current_posL[1]) > 20:
                        print(f"[DEBUG] 正在修正位置误差...")
                        posL = current_posL
                    else:
                        print(f"[WARNING] 队长位置已发生变化!")
                    
                if not posL:
                    print("[ERROR] 获取队长位置失败，无法继续战斗")
                    timeout_mgr.stop_monitoring(argv.node_name)
                    return False
                base_action_data, loop_action_data = analyze_data(action_data)
                list_completed, current_pos_data = list_combat(pos_data, base_action_data, posL)
                if loop_action_data and list_completed:
                    print("[DEBUG] 基础执行完成，开始循环战斗...")
                    loop_completed, _ = loop_combat(current_pos_data, loop_action_data, posL)
                    if loop_completed:
                        print("[DEBUG] 循环战斗已完成")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return True
                    else: 
                        print("[WARNING] 循环战斗未完成，将按当前进度退出")
                    timeout_mgr.stop_monitoring(argv.node_name)
                    return False
                else:
                    if list_completed:
                        print("[DEBUG] 基础执行完成")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return True
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        try:
            return main()
        finally:
            timeout_mgr.stop_monitoring(argv.node_name)
