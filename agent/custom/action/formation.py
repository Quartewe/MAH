from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from pathlib import Path
import json
import re
import time
from utils import logger, timeout_mgr, data_io, act_mgr, match_mgr, proj_path, info_share

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
        # 1280x720 编队界面右下角的 TOTAL COST 数值区域。
        # 只读取数值区域，避免把角色卡片上的 9/35、1/30 等等级文本当成队伍消耗。
        self.TEAM_COST_ROI = [1120, 495, 155, 75]
        self.COST_ERROR_ROI = [390, 220, 490, 170]
        self.COST_CONFIRM_ROI = [520, 430, 270, 130]

    def _normalize_template_path(self, raw_path):
        return act_mgr.normalize_template_path(raw_path) or ""

    @staticmethod
    def _normalize_character_id(char_id):
        if isinstance(char_id, int):
            return f"{char_id:02d}"
        if char_id is None:
            return ""
        char_id = str(char_id).strip()
        return char_id.zfill(2) if char_id.isdigit() else char_id

    def _get_character_info(self, character):
        """返回角色筛选信息和是否为低星角色。"""
        if not isinstance(character, dict):
            return {}, False

        name = str(character.get("name", "")).strip()
        element = str(character.get("element", "")).strip()
        if element:
            lowstar_data = self.CHAR_LOWSTAR_DATA.get(name, {})
            variant = lowstar_data.get(element, {})
            if not isinstance(variant, dict):
                variant = {}
            info = dict(lowstar_data) if isinstance(lowstar_data, dict) else {}
            info.update(variant)
            info["element"] = element
            if info.get("weapon") == "varies":
                info["weapon"] = variant.get("weapon", "")
            return info, True

        char_id = self._normalize_character_id(character.get("id"))
        char_data = self.CHAR_DATA.get(name, {})
        if not isinstance(char_data, dict):
            return {}, False
        info = char_data.get(char_id, {})
        return (info if isinstance(info, dict) else {}), False

    def _template_path_exists(self, raw_path):
        normalized_path = self._normalize_template_path(raw_path)
        if not normalized_path:
            return False

        path = Path(normalized_path)
        if path.is_absolute():
            return path.exists()

        roots = (
            proj_path.IMAGE_DIR,
            proj_path.RESOURCE_DIR / "base" / "image",
            proj_path.RESOURCE_DIR / "image",
        )
        return any((root / path).exists() for root in roots)

    def _validate_team_resources(self, team_data):
        """阻止索引或模板不完整时进入无效编队。"""
        errors = []
        if not self.UI_DATA:
            errors.append(f"缺少 UI 索引: {proj_path.UI_FILE}")

        role_items = [
            (key, value)
            for key, value in team_data.items()
            if key != "community" and isinstance(value, dict)
        ]
        if not role_items:
            errors.append("队伍中没有可用角色")

        for role_key, character in role_items:
            name = str(character.get("name", "")).strip()
            info, _ = self._get_character_info(character)
            if not name or not info:
                errors.append(f"{role_key}: 角色索引不存在 ({name})")
                continue

            if not self._template_path_exists(info.get("path")):
                errors.append(f"{role_key}: 角色模板不存在 ({name})")

            element = info.get("element")
            rarity = info.get("rarity")
            weapon = info.get("weapon")
            if self.UI_DATA:
                if not self.UI_DATA.get("element", {}).get(element):
                    errors.append(f"{role_key}: 属性筛选模板不存在 ({element})")
                if not self.UI_DATA.get("rarity", {}).get(str(rarity)):
                    errors.append(f"{role_key}: 稀有度筛选模板不存在 ({rarity})")
                if not self.UI_DATA.get("weapon", {}).get(weapon):
                    errors.append(f"{role_key}: 武器筛选模板不存在 ({weapon})")

            ar_name = character.get("AR")
            if ar_name:
                ar_data = self.AR_DATA.get(ar_name, {})
                if not isinstance(ar_data, dict) or not ar_data.get("path"):
                    errors.append(f"{role_key}: AR 索引不存在 ({ar_name})")
                elif not self._template_path_exists(ar_data.get("path")):
                    errors.append(f"{role_key}: AR 模板不存在 ({ar_name})")

        community = team_data.get("community")
        if community and not self._get_community_template_path(community):
            errors.append(f"工会模板不存在 ({community})")

        return errors

    @staticmethod
    def _normalize_ocr_text(text):
        translation = str.maketrans(
            {
                "編": "编",
                "隊": "队",
                "組": "组",
                "請": "请",
                "減": "减",
                "確": "确",
                "認": "认",
                "過": "过",
                "値": "值",
            }
        )
        normalized = str(text or "").lower().translate(translation)
        return re.sub(r"[\s\u3000，。,.！？!：:；;（）()\"'“”‘’]", "", normalized)

    @classmethod
    def _is_cost_error_text(cls, text):
        normalized = cls._normalize_ocr_text(text)
        if not normalized:
            return False

        chinese_or_japanese = (
            "超" in normalized
            and any(token in normalized for token in ("编队", "编成", "编组"))
            and any(
                token in normalized
                for token in ("消耗", "コスト", "cost", "上限", "最大")
            )
        )
        reduce_cost = "减少" in normalized and any(
            token in normalized for token in ("消耗", "コスト", "cost")
        )
        english = "cost" in normalized and any(
            token in normalized
            for token in ("exceed", "maximum", "limit", "reduce", "over")
        )
        return chinese_or_japanese or reduce_cost or english

    @classmethod
    def _is_confirm_text(cls, text):
        normalized = cls._normalize_ocr_text(text)
        return normalized in {
            "确定",
            "确认",
            "ok",
            "confirm",
            "close",
            "閉じる",
        }

    @staticmethod
    def _parse_team_cost_text(text):
        """解析编队界面上的“当前消耗/最大消耗”，不依赖账号等级。"""
        if not text:
            return None

        normalized = str(text).strip()
        normalized = normalized.replace("／", "/").replace("∕", "/")
        normalized = normalized.replace("丨", "/").replace("|", "/")
        match = re.search(r"(?<!\d)(\d{1,3})\s*/\s*(\d{1,3})(?!\d)", normalized)
        if not match:
            return None

        return int(match.group(1)), int(match.group(2))

    def _read_team_cost(self, context, retries=3):
        """从当前编队画面读取动态队伍消耗上限。"""
        for attempt in range(1, retries + 1):
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            result = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "threshold": 0.7,
                                "roi": self.TEAM_COST_ROI,
                                "expected": [""],
                            }
                        }
                    }
                },
            )

            for candidate in result.all_results:
                cost = self._parse_team_cost_text(getattr(candidate, "text", ""))
                if cost:
                    logger.info(
                        f"动态编队消耗: {cost[0]}/{cost[1]} "
                        f"(第 {attempt}/{retries} 次读取)"
                    )
                    return cost

            if attempt < retries:
                time.sleep(0.25)

        logger.warning("未能从编队界面读取动态消耗上限")
        return None

    def _dismiss_cost_error(self, context):
        """仅在确认超限正文存在时关闭弹窗，并返回弹窗是否出现。"""
        context.tasker.controller.post_screencap().wait()
        current_image = context.tasker.controller.cached_image
        message_result = context.run_recognition(
            "UtilsOCR",
            current_image,
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "threshold": 0.7,
                            "roi": self.COST_ERROR_ROI,
                            "expected": [""],
                        }
                    }
                }
            },
        )

        message_text = " ".join(
            str(getattr(candidate, "text", ""))
            for candidate in message_result.all_results
        )
        if not self._is_cost_error_text(message_text):
            return False

        confirm_result = context.run_recognition(
            "UtilsOCR",
            current_image,
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "threshold": 0.7,
                            "roi": self.COST_CONFIRM_ROI,
                            "expected": [""],
                        }
                    }
                }
            },
        )
        confirm_result = next(
            (
                candidate
                for candidate in confirm_result.all_results
                if self._is_confirm_text(getattr(candidate, "text", ""))
            ),
            None,
        )
        if not confirm_result:
            logger.error("检测到编队消耗超限提示，但未识别到确认按钮")
            return True

        confirm_box = getattr(confirm_result, "box", None)
        if not confirm_box or len(confirm_box) < 4:
            logger.error(f"编队消耗超限确认按钮位置无效: {confirm_box}")
            return True

        context.run_action(
            "UtilsClick",
            confirm_box,
            pipeline_override={
                "UtilsClick": {
                    "action": {
                        "param": {
                            "target": confirm_box,
                        }
                    }
                }
            },
        )
        logger.info("已关闭编队消耗超限提示")
        return True

    def _get_community_template_path(self, community):
        """优先使用索引，索引未生成时回退到仓库内的标准工会图片路径。"""
        indexed_path = self._normalize_template_path(
            self.UI_DATA.get("community", {}).get(community, "")
        )
        if indexed_path and self._template_path_exists(indexed_path):
            return indexed_path
        if indexed_path:
            logger.warning(f"工会索引路径不存在: {community} -> {indexed_path}")

        fallback = f"fight/community/community_{community}.png"
        if self._template_path_exists(fallback):
            logger.warning(
                f"未找到工会索引 {community}，使用标准模板路径: {fallback}"
            )
            return fallback
        return ""

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
        logger.info(f"目标文件: {param}")
        if not param:
            logger.info(f"未指定要搜索的目标文件")
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
                logger.info(f"当前已处于自动战斗模式，正在关闭...")
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
                logger.info(f"当前未处于自动战斗模式，无需关闭")
            info_share.auto_combat_mode = False
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        try:
            raw_data = data_io.find_target_files(self.DATA_PATH, param)
            team_data = raw_data.get("team", None)
            logger.info(f"助战数据: {team_data}")
        except Exception as e:
            logger.error(f"查找目标文件失败: {e}")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False
        if not team_data:
            logger.warning(f"无team数据, 跳过角色选择")
            timeout_mgr.stop_monitoring(argv.node_name)
            return True

        resource_errors = self._validate_team_resources(team_data)
        if resource_errors:
            logger.error(
                "编队资源未就绪，未执行解散队伍: " + "; ".join(resource_errors)
            )
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        lang_mode = act_mgr.detect_lang(
            context,
            [1087, 88, 191, 633],
            ignore=info_share.IGNORE_LIST,
        )
        markers = {
            "jp": ["編成解散", "OK", "OK"],
            "cn": ["解散队伍", "OK", "确定"],
            "tw": ["解散編組", "OK", "OK"],
            "en": ["Disband", "OK", "OK"],
        }.get(lang_mode)
        if markers is None:
            logger.warning(f"未能确定编队界面语言: {lang_mode}，默认使用简体中文")
            markers = ["解散队伍", "OK", "确定"]


        # 清除可能存在的旧数据
        logger.info(f"正在解散旧队伍...")
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
        logger.info(f"旧队伍已解散，开始新编组...")

        initial_team_cost = self._read_team_cost(context)
        if not initial_team_cost:
            logger.error("无法读取账号动态编队消耗，停止编队以避免使用错误上限")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False
        logger.info(
            f"账号当前编队消耗上限为 {initial_team_cost[1]}，"
            "后续按界面实时值校验，不使用固定上限"
        )

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
        if raw_title is None:
            logger.error("无法识别编队槽位标题，未继续编队")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

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

        title_results = list(getattr(raw_title, "filtered_results", []) or [])
        title_results = sorted(title_results, key=lambda x: x.box[0])
        raw_title.filtered_results = title_results

        support_target_pos = _get_support_target_pos(team_data)
        support_source_pos = None
        for idx, title in enumerate(raw_title.filtered_results):
            if match_mgr.fuzzy_match(title.text, "SUPPORT"):
                support_source_pos = idx + 1
                break

        if support_source_pos is None:
            logger.error("未识别到当前 SUPPORT 槽位，未继续编队")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        target_role_map = _build_target_role_map(team_data)
        combat_role_list = _build_combat_role_list(
            target_role_map,
            support_source_pos,
            support_target_pos,
            len(title_results),
        )
        combat_role_idx = 0

        expected_combat_roles = sum(
            1
            for key in team_data
            if key not in ("LEADER", "SUPPORT", "community")
        ) + (1 if team_data.get("LEADER") else 0)
        if len(combat_role_list) != expected_combat_roles:
            logger.error(
                f"编队槽位识别不完整: 识别到 {len(title_results)} 个槽位，"
                f"可配置角色 {expected_combat_roles} 个，未继续编队"
            )
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        logger.info(f"助战来源位置={support_source_pos}, 助战目标位置={support_target_pos}")
        logger.info(f"战斗角色列表={combat_role_list}")

        
        # 计算 team_data 中的最大索引
        # 选择角色
        for idx, title in enumerate(title_results):
            lowstar_mode = False
            current_pos = idx + 1
            logger.info(f"当前位置标题: {title.text}")
            logger.info(f"当前序号: {current_pos}")

            # 运行时当前 SUPPORT 槽位始终跳过，留给最后换位处理
            if match_mgr.fuzzy_match(title.text, "SUPPORT"):
                logger.info(f"跳过运行时助战槽位: {current_pos}")
                continue

            role_key = None
            if combat_role_idx < len(combat_role_list):
                role_key = combat_role_list[combat_role_idx]
                combat_role_idx += 1

            if not role_key:
                logger.info(f"位置 {current_pos} 未配置角色，跳过")
                continue

            current_char = team_data.get("LEADER") if role_key == "LEADER" else team_data.get(role_key, None)
            if not current_char:
                logger.info(f"位置 {current_pos} 的角色 {role_key} 缺少队伍数据，跳过")
                continue
            
            logger.info(f"当前角色数据: {current_char}")
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
            current_char_id = self._normalize_character_id(current_char.get("id"))
            current_lowchar_element = current_char.get("element", "")
            current_char_info, lowstar_mode = self._get_character_info(current_char)
            current_char_element = current_char_info.get("element", "")
            current_char_rarity = current_char_info.get("rarity", 0)
            current_char_weapon = current_char_info.get("weapon", "")
            
            logger.info(f"当前角色稀有度: {current_char_rarity}")
            logger.info(f"当前角色属性: {current_char_element}")
            logger.info(f"当前角色武器: {current_char_weapon}")
            if not act_mgr.choose_filter(
                context,
                current_char_element,
                current_char_rarity,
                current_char_weapon,
            ):
                logger.error(f"角色筛选失败: {current_char_name}")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
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
            choose_results = list(
                getattr(choose_finish, "filtered_results", []) or []
            )
            if len(choose_results) != 1:
                logger.error(f"无法确认角色选择: {current_char_name} (ID: {current_char_id})")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
            
            # 获取第一个识别结果的位置
            target_box = choose_results[0].box
            if not target_box or len(target_box) < 4 or target_box[2] <= 0 or target_box[3] <= 0:
                logger.error(f"角色识别框无效: {current_char_name} -> {target_box}")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
            logger.info(f"{current_char_name} 的目标点击框: {target_box}")
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

            updated_team_cost = self._read_team_cost(context)
            if self._dismiss_cost_error(context):
                logger.error(
                    f"角色 {current_char_name} 触发编队消耗限制，"
                    "已停止当前编队，请使用更低消耗角色或调整编队文件"
                )
                timeout_mgr.stop_monitoring(argv.node_name)
                return False

            if updated_team_cost and updated_team_cost[0] > updated_team_cost[1]:
                self._dismiss_cost_error(context)
                logger.error(
                    f"选择 {current_char_name} 后编队消耗 "
                    f"{updated_team_cost[0]}/{updated_team_cost[1]} 超出账号动态上限，"
                    "已停止继续编队，请使用更低消耗角色或调整编队文件"
                )
                timeout_mgr.stop_monitoring(argv.node_name)
                return False

            if not updated_team_cost:
                logger.error(
                    f"选择 {current_char_name} 后无法读取动态编队消耗，"
                    "停止继续编队"
                )
                timeout_mgr.stop_monitoring(argv.node_name)
                return False

            # 只有角色确认加入队伍后才记录 AR，确保 AR 列表与已编入角色槽位一致。
            ar_list.append(current_char_ar)

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
        support_results = list(
            getattr(support_title, "filtered_results", []) or []
        )
        support_results = sorted(support_results, key=lambda x: x.box[0])
        if not support_results:
            logger.error("填充角色后无法识别编队槽位标题，未执行 SUPPORT 换位")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        support_source_pos = None
        support_source_box = None
        for idx, title in enumerate(support_results):
            if match_mgr.fuzzy_match(title.text, "SUPPORT"):
                support_source_pos = idx + 1
                support_source_box = title.box
                break

        if support_source_pos is None or not support_source_box:
            logger.error("填充角色后未识别到 SUPPORT 槽位，未执行换位")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        if (
            support_source_pos
            and support_source_box
            and support_source_pos != support_target_pos
            and 1 <= support_target_pos <= len(support_results)
        ):
            support_target_box = support_results[support_target_pos - 1].box
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
            community_path = self._get_community_template_path(team_community)
            if not community_path:
                logger.error(f"工会模板路径无效: {team_community}")
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
                    logger.error(f"未找到工会: {team_community}")
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
            ar_results = list(getattr(ar_select, "filtered_results", []) or [])
            for ar, pos in zip(ar_list, ar_results):
                logger.info(f"当前 AR: {ar}")
                logger.info(f"当前 AR 位置: {pos.box}")
                if not ar:
                    logger.info("当前角色未指定 AR，保留默认配置")
                    continue
                current_ar_data = self.AR_DATA.get(ar, "")
                if not isinstance(current_ar_data, dict):
                    logger.error(f"AR 索引数据无效: {ar}")
                    continue
                current_ar_rarity = current_ar_data.get("rarity", 0)
                ar_path = self._normalize_template_path(current_ar_data.get("path"))
                if not ar_path:
                    logger.error(f"AR 模板路径无效: {ar}")
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
                    logger.info(f"AR 选择结果: {choose_ar}")
                    if not choose_ar.best_result:
                        logger.warning(f"选择 AR 失败: {ar}，正在重试...")
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
                            logger.error(f"多次尝试后仍无法选择 AR: {ar}，跳过...")
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
            logger.info(f"当前已处于自动战斗模式，正在关闭...")
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
            logger.info(f"当前未处于自动战斗模式，无需关闭")
        info_share.auto_combat_mode = False


        timeout_mgr.stop_monitoring(argv.node_name)
        return True
