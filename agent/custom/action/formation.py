from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from pathlib import Path
import json
from utils import timeout_mgr, data_io, act_mgr, match_mgr, proj_path, info_share

@AgentServer.custom_action("Formation")
class Formation(CustomAction):
    def __init__(self):
        super().__init__()
        self.DATA_PATH = proj_path.AUTO_COMBAT_DIR
        self.CHAR_DATA = data_io.read_data(proj_path.CHAR_FILE)
        self.CHAR_LOWSTAR_DATA = data_io.read_data(proj_path.CHAR_LOWSTAR_FILE)
        self.AR_DATA = data_io.read_data(proj_path.AR_FILE)
        self.UI_DATA = data_io.read_data(proj_path.UI_FILE)
        self.TITLE_ROI = [20, 95, 1035, 55]

    def _normalize_template_path(self, raw_path):
        if not raw_path:
            return ""

        path_str = str(raw_path).replace("\\", "/").lstrip("./")
        image_root_rel = proj_path.IMAGE_DIR.relative_to(proj_path.PROJECT_ROOT).as_posix()
        prefix = f"{image_root_rel}/"

        if path_str.startswith(prefix):
            return path_str[len(prefix):]
        return path_str

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        if timeout_mgr.check_timeout(argv.node_name):
            return False
        
        ar_list = []
        click_box = [0,0,120,120]
        context.tasker.controller.post_screencap().wait()
        current_image = context.tasker.controller.cached_image
        param = argv.custom_action_param
        if isinstance(param, str):
            param = param.strip('"')
        print(f"[DEBUG] 目标文件: {param}")
        if not param:
            print(f"[DEBUG] 未指定要搜索的目标文件")
            auto_mode = context.run_recognition(
            "UtilsOCR",
            current_image,
            pipeline_override={
                "UtilsOCR":{
                    "recognition":{
                        "param":{
                            "roi": [863,5,157,82],
                            "expected": "ON"
                            }
                        }
                    }
                }
            )
            if auto_mode.best_result:
                print(f"[DEBUG] 当前已处于自动战斗模式，正在关闭...")
                context.run_action(
                    "UtilsClick",
                    auto_mode.best_result.box,
                    pipeline_override={
                        "UtilsClick": {
                            "action": {
                                "param": {
                                    "target": auto_mode.best_result.box
                                }
                            }
                        }
                    }
                )
            else:
                print(f"[DEBUG] 当前未处于自动战斗模式，无需关闭")
            info_share.auto_combat_mode = False
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        try:
            raw_data = data_io.find_target_files(self.DATA_PATH, param)
            team_data = raw_data.get("team", None)
            print(f"[DEBUG] 助战数据: {team_data}")
        except Exception as e:
            print(f"[ERROR] 查找目标文件失败: {e}")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False
        if not team_data:
            print(f"[WARNING] 无team数据, 跳过角色选择")
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        lang_mode = act_mgr.detect_lang(context, [1087,88,191,633])
        if lang_mode == "jp":
            markers = ["編成解散", "OK", "OK"]
        if lang_mode == "cn":
            markers = ["解散队伍", "OK", "确定"]
        if lang_mode == "tw":
            markers = ["解散編組", "OK", "OK"]
        if lang_mode == "en":
            markers = ["Disband", "OK", "OK"]


        # 清除可能存在的旧数据
        print(f"[DEBUG] 正在解散旧队伍...")
        context.run_task(
            "UtilsOCR",
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "roi": [1087,88,191,633],
                            "expected": markers[0]
                        }
                    },
                    "action": {
                        "type": "Click"
                    }
                }
            }
        )
        context.run_task(
            "UtilsOCR",
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "roi": [261,401,748,218],
                            "expected": markers[1]
                        }
                    },
                    "action": {
                        "type": "Click"
                    }
                }
            }
        )
        context.run_task(
            "UtilsOCR",
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "roi": [261,401,748,218],
                            "expected": markers[2]
                        }
                    },
                    "action": {
                        "type": "Click"
                    }
                }
            }
        )
        print(f"[DEBUG] 旧队伍已解散，开始新编组...")

        context.tasker.controller.post_screencap().wait()
        current_image = context.tasker.controller.cached_image

        raw_title = context.run_recognition(
            "UtilsOCR",
            current_image,
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "threshold": 0.93,
                            "roi": self.TITLE_ROI
                        }
                    }
                }
            }
        )

        def _get_support_target_pos(team_info: dict) -> int:
            pos = 1
            for key in team_info.keys():
                if key in ["LEADER", "community"]:
                    continue
                pos += 1
                if str(key).upper() == "SUPPORT":
                    return pos
            return 6

        def _build_target_role_map(team_info: dict) -> dict:
            role_map = {1: "LEADER"}
            pos = 1
            for key in team_info.keys():
                if key in ["LEADER", "community"]:
                    continue
                pos += 1
                if str(key).upper() == "SUPPORT":
                    role_map[pos] = "SUPPORT"
                else:
                    role_map[pos] = str(key)
            return role_map

        def _build_combat_role_list(
            target_map: dict,
            support_source: int | None,
            support_target: int,
            total_slots: int,
        ) -> list[str]:
            def _runtime_pos_to_final_pos(pos: int) -> int:
                if not support_source or support_source == support_target:
                    return pos

                # SUPPORT 从左往右拖：中间槽位在最终阵容中整体前移
                if support_source < support_target:
                    if support_source < pos <= support_target:
                        return pos - 1
                    return pos

                # SUPPORT 从右往左拖：中间槽位在最终阵容中整体后移
                if support_target <= pos < support_source:
                    return pos + 1
                return pos

            combat_roles = []
            for pos in range(1, total_slots + 1):
                if support_source and pos == support_source:
                    continue

                final_pos = _runtime_pos_to_final_pos(pos)
                role_key = target_map.get(final_pos, None)
                if not role_key or role_key == "SUPPORT":
                    continue
                combat_roles.append(role_key)

            return combat_roles

        raw_title.filtered_results = sorted(raw_title.filtered_results, key=lambda x: x.box[0])

        support_target_pos = _get_support_target_pos(team_data)
        support_source_pos = None
        for idx, title in enumerate(raw_title.filtered_results):
            if match_mgr.fuzzy_match(title.text, "SUPPORT"):
                support_source_pos = idx + 1
                break

        target_role_map = _build_target_role_map(team_data)
        combat_role_list = _build_combat_role_list(
            target_role_map,
            support_source_pos,
            support_target_pos,
            len(raw_title.filtered_results),
        )
        combat_role_idx = 0

        print(f"[DEBUG] 助战来源位置={support_source_pos}, 助战目标位置={support_target_pos}")
        print(f"[DEBUG] 战斗角色列表={combat_role_list}")

        
        # 计算 team_data 中的最大索引
        # 选择角色
        for idx, title in enumerate(raw_title.filtered_results):
            lowstar_mode = False
            current_pos = idx + 1
            print(f"[DEBUG] 当前位置标题: {title.text}")
            print(f"[DEBUG] 当前序号: {current_pos}")

            # 运行时当前 SUPPORT 槽位始终跳过，留给最后换位处理
            if match_mgr.fuzzy_match(title.text, "SUPPORT"):
                print(f"[DEBUG] 跳过运行时助战槽位: {current_pos}")
                continue

            role_key = None
            if combat_role_idx < len(combat_role_list):
                role_key = combat_role_list[combat_role_idx]
                combat_role_idx += 1

            if not role_key:
                print(f"[DEBUG] 位置 {current_pos} 未配置角色，跳过")
                continue

            current_char = team_data.get("LEADER") if role_key == "LEADER" else team_data.get(role_key, None)
            if not current_char:
                print(f"[DEBUG] 位置 {current_pos} 的角色 {role_key} 缺少队伍数据，跳过")
                continue
            
            print(f"[DEBUG] 当前角色数据: {current_char}")
            click_box[0] = title.box[0] - 35
            click_box[1] = title.box[1] + 105
            click_res = context.run_action(
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
            current_char_name = current_char.get("name", "")
            current_char_ar = current_char.get("AR", None)
            ar_list.append(current_char_ar)
            current_char_id = current_char.get("id", "")
            if isinstance(current_char_id, int):
                current_char_id = f"{current_char_id:02d}"
            current_lowchar_element = current_char.get("element", "")
            if current_lowchar_element:
                lowstar_mode = True
            if not lowstar_mode:
                current_char_info = self.CHAR_DATA.get(current_char_name, {}).get(current_char_id, {})
                current_char_element = current_char_info.get("element", "")
                current_char_rarity = current_char_info.get("rarity", 0)
                current_char_weapon = current_char_info.get("weapon", "")
            if lowstar_mode:
                current_char_info = self.CHAR_LOWSTAR_DATA.get(current_char_name, {})
                current_char_rarity = current_char_info.get("rarity", 0)
                
                current_char_weapon = current_char_info.get("weapon", "")
                current_char_element = current_lowchar_element
                if current_char_weapon == "varies":
                    current_char_weapon = current_char_info.get(current_char_element, {}).get("weapon", "")
            
            print(f"[DEBUG] 当前角色稀有度: {current_char_rarity}")
            print(f"[DEBUG] 当前角色属性: {current_char_element}")
            print(f"[DEBUG] 当前角色武器: {current_char_weapon}")
            act_mgr.choose_filter(context, current_char_element, current_char_rarity, current_char_weapon)
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            choose_finish = context.run_recognition(
                "TraverseMatch",
                current_image,
                pipeline_override={
                    "TraverseMatch":{
                        "recognition":{
                            "type": "Custom",
                            "param":{
                                "custom_recognition": "TraverseMatch",
                                "custom_recognition_param":{
                                    "name": current_char_name,
                                    "id": current_char_id,
                                    "element": current_lowchar_element
                                }
                            }
                        }
                    }
                }
            )
            # 检查是否有识别结果
            if len(choose_finish.filtered_results) > 1 or not choose_finish.filtered_results:
                print(f"[ERROR] 无法确认角色选择: {current_char_name} (ID: {current_char_id})")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
            
            # 获取第一个识别结果的位置
            target_box = choose_finish.filtered_results[0].box
            print(f"[DEBUG] {current_char_name} 的目标点击框: {target_box}")
            context.run_action(
                "UtilsClick",
                target_box,
                pipeline_override={
                    "UtilsClick": {
                        "action": {
                            "param": {
                                "target": target_box
                            }
                        }
                    }
                }
            )

        # 其他槽位填充完成后，再处理 SUPPORT 槽位换位
        context.tasker.controller.post_screencap().wait()
        current_image = context.tasker.controller.cached_image
        support_title = context.run_recognition(
            "UtilsOCR",
            current_image,
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "threshold": 0.93,
                            "roi": self.TITLE_ROI
                        }
                    }
                }
            }
        )
        support_title.filtered_results = sorted(support_title.filtered_results, key=lambda x: x.box[0])
        support_source_pos = None
        support_source_box = None
        for idx, title in enumerate(support_title.filtered_results):
            if match_mgr.fuzzy_match(title.text, "SUPPORT"):
                support_source_pos = idx + 1
                support_source_box = title.box
                break

        if (
            support_source_pos
            and support_source_box
            and support_source_pos != support_target_pos
            and 1 <= support_target_pos <= len(support_title.filtered_results)
        ):
            support_target_box = support_title.filtered_results[support_target_pos - 1].box
            print(
                f"[DEBUG] 填充后移动 SUPPORT: 来源={support_source_pos}, 目标={support_target_pos}"
            )
            context.run_action(
                "UtilsSwipe",
                pipeline_override={
                    "UtilsSwipe": {
                        "action": {
                            "type": "Swipe",
                            "param": {
                                "begin": support_source_box,
                                "end": support_target_box
                            }
                        }
                    }
                }
            )

        # 选择工会    
        team_community = team_data.get("community", None)
        if team_community:
            community_path = self._normalize_template_path(
                self.UI_DATA.get("community", {}).get(team_community, "")
            )
            if not community_path:
                print(f"[ERROR] 工会模板路径无效: {team_community}")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
            enter_finish = context.run_task(
                "UtilsFeatureMatch",
                pipeline_override={
                    "UtilsFeatureMatch":{
                        "recognition":{
                            "param":{
                                "roi": [1086,87,189,400],
                                "template": "fight/community/community_empty.png"
                            }
                        },
                        "action":{
                            "type": "Click"
                        }
                    }
                }
            )
            if enter_finish:
                max_search_rounds = 6
                community_found = False
                for _ in range(max_search_rounds):
                    first_page = context.run_task(
                        "UtilsFeatureMatch",
                        pipeline_override={
                            "UtilsFeatureMatch": {
                                "recognition": {
                                    "param": {
                                        "template": str(community_path)
                                    }
                                },
                                "action": {
                                    "type": "Click"
                                },
                                "timeout": 10000
                            }
                        }
                    )
                    if first_page:
                        community_found = True
                        break

                    context.run_action(
                        "UtilsSwipe",
                        pipeline_override={
                            "UtilsSwipe": {
                                "action": {
                                    "type": "Swipe",
                                    "param": {
                                        "begin": [970,642,70,27],
                                        "end": [961,39,88,22]
                                    }
                                }
                            }
                        }
                    )

                    second_page = context.run_task(
                        "UtilsFeatureMatch",
                        pipeline_override={
                            "UtilsFeatureMatch": {
                                "recognition": {
                                    "param": {
                                        "template": str(community_path)
                                    }
                                },
                                "action": {
                                    "type": "Click"
                                },
                                "timeout": 0
                            }
                        }
                    )
                    if second_page:
                        community_found = True
                        break

                    context.run_action(
                        "UtilsSwipe",
                        pipeline_override={
                            "UtilsSwipe": {
                                "action": {
                                    "type": "Swipe",
                                    "param": {
                                        "begin": [966,100,68,24],
                                        "end": [970,642,70,27]
                                    }
                                }
                            }
                        }
                    )

                if not community_found:
                    print(f"[ERROR] 未找到工会: {team_community}")
                    timeout_mgr.stop_monitoring(argv.node_name)
                    return False

                lang_mode = act_mgr.detect_lang(context, [199,23,540,51])
                if lang_mode == "jp":
                    markers = ["設定"]
                if lang_mode == "cn":
                    markers = ["设定"]
                if lang_mode == "tw":
                    markers = ["設定"]
                if lang_mode == "en":
                    markers = ["Activate"]
                for marker, roi in zip(markers, [[403,624,348,99]]):
                    community_finish = context.run_task(
                        "UtilsOCR",
                        pipeline_override={
                            "UtilsOCR": {
                                "recognition": {
                                    "param": {
                                        "roi": roi,
                                        "expected": marker
                                    }
                                },
                                "action":{
                                    "type": "Click"
                                }
                            }
                        }
                    )

        # 选择AR
        if ar_list:
            import time
            break_time = 0
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            ar_select = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR":{
                        "recognition":{
                            "param":{
                                "roi": [21,585,1033,96],
                                "expected": "AR"
                            }
                        }
                    }
                }
            )
            for ar, pos in zip(ar_list, ar_select.filtered_results):
                print(f"[DEBUG] 当前 AR: {ar}")
                print(f"[DEBUG] 当前 AR 位置: {pos.box}")
                current_ar_data = self.AR_DATA.get(ar, "")
                current_ar_rarity = current_ar_data.get("rarity", 0)
                ar_path = self._normalize_template_path(current_ar_data.get("path"))
                if not ar_path:
                    print(f"[ERROR] AR 模板路径无效: {ar}")
                    continue
                context.run_action(
                    "UtilsClick",
                    pos.box,
                    pipeline_override={
                        "UtilsClick": {
                            "action": {
                                "param": {
                                    "target": pos.box
                                }
                            }
                        }
                    }
                )
                act_mgr.choose_filter(context, rarity = current_ar_rarity, AR_mode=True)
                while True:
                    context.tasker.controller.post_screencap().wait()
                    current_image = context.tasker.controller.cached_image
                    choose_ar = context.run_recognition(
                        "UtilsFeatureMatch",
                        current_image,
                        pipeline_override={
                            "UtilsFeatureMatch": {
                                "recognition": {
                                    "param": {
                                        "template": str(ar_path)
                                    }
                                },
                            }
                        }
                    )
                    print(f"[DEBUG] AR 选择结果: {choose_ar}")
                    if not choose_ar.best_result:
                        print(f"[WARNING] 选择 AR 失败: {ar}，正在重试...")
                        break_time += 1
                        context.run_action(
                            "UtilsSwipe",
                            pipeline_override={
                                "UtilsSwipe": {
                                    "action": {
                                        "type": "Swipe",
                                        "param": {
                                            "begin": [803,418,10,10],
                                            "end": [803,74,10,10]
                                        }
                                    }
                                }
                            }
                        )
                        if break_time >= 20:
                            print(f"[ERROR] 多次尝试后仍无法选择 AR: {ar}，跳过...")
                            break
                    else:
                        for _ in range(2):
                            context.run_action(
                                "UtilsClick",
                                choose_ar.best_result.box,
                                pipeline_override={
                                    "UtilsClick": {
                                        "action": {
                                            "param": {
                                                "target": choose_ar.best_result.box
                                            }
                                        }
                                    }
                                }
                            )
                            time.sleep(0.5)
                        break
            
        context.tasker.controller.post_screencap().wait()
        current_image = context.tasker.controller.cached_image
        auto_mode = context.run_recognition(
            "UtilsOCR",
            current_image,
            pipeline_override={
                "UtilsOCR":{
                    "recognition":{
                        "param":{
                            "roi": [863,5,157,82],
                            "expected": "ON"
                            }
                        }
                    }
                }
            )
        if auto_mode.best_result:
            print(f"[DEBUG] 当前已处于自动战斗模式，正在关闭...")
            context.run_action(
                "UtilsClick",
                auto_mode.best_result.box,
                pipeline_override={
                    "UtilsClick": {
                        "action": {
                            "param": {
                                "target": auto_mode.best_result.box
                            }
                        }
                    }
                }
            )
        else:
            print(f"[DEBUG] 当前未处于自动战斗模式，无需关闭")
        info_share.auto_combat_mode = False


        timeout_mgr.stop_monitoring(argv.node_name)
        return True