from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import time
import json
from utils import logger, data_io, timeout_mgr, proj_path


_TEXT_VARIANT_PAIRS = (
    ("（", "("),
    ("）", ")"),
    ("试", "試"),
    ("炼", "煉"),
    ("击", "擊"),
    ("斩", "斬"),
    ("横", "橫"),
    ("无", "無"),
)


def _text_variants(text):
    variants = [text]
    for left, right in _TEXT_VARIANT_PAIRS:
        expanded = []
        for value in variants:
            for candidate in (value, value.replace(left, right), value.replace(right, left)):
                if candidate not in expanded:
                    expanded.append(candidate)
        variants = expanded
    return variants


def normalize_brackets(data):
    """Generate OCR aliases for mixed simplified/traditional text and brackets."""
    if not data:
        return None

    if isinstance(data, list):
        result = []
        for item in data:
            normalized = normalize_brackets(item)
            if normalized is None:
                continue
            values = normalized if isinstance(normalized, list) else [normalized]
            for value in values:
                if value not in result:
                    result.append(value)
        return result

    variants = _text_variants(str(data))
    return variants[0] if len(variants) == 1 else variants


@AgentServer.custom_action("QuestSelect")
class QuestSelect(CustomAction):
    def __init__(self):
        super().__init__()
        self.last_len = 0

    @staticmethod
    def _recognize_quests(context: Context, folder_name):
        context.tasker.controller.post_screencap().wait()
        current_image = context.tasker.controller.cached_image
        return context.run_recognition(
            "UtilsOCR",
            current_image,
            pipeline_override={
                "UtilsOCR": {
                    "pre_wait_freeze": {
                        "time": 1000,
                        "target": [0, 0, 1080, 720],
                        "threshold": 0.999
                    },
                    "recognition": {
                        "param": {
                            "roi": [494, 3, 779, 671],
                            "duration": 200,
                            "expected": folder_name,
                            "order_by": "Vertical"
                        }
                    }
                }
            }
        )

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):    
            return False
        
        param = json.loads(argv.custom_action_param)
        logger.info(f"原始参数: {param}")
        tile_mode = False
        folder_name = normalize_brackets(param.get("name", ""))
        difficulty = normalize_brackets(param.get("difficulty", ""))
        difficulty = difficulty + "級" if difficulty in ["初", "中", "上"] else difficulty
        if not difficulty:
            logger.info(f"平铺模式")
            tile_mode = True
        
        logger.info(f"目标任务名: {folder_name}")
        logger.info(f"目标难度: {difficulty}")
        difficulty_candidates = difficulty if isinstance(difficulty, list) else [difficulty]
        difficulty_candidates = [d for d in difficulty_candidates if isinstance(d, str) and d]
        logger.info(f"难度候选: {difficulty_candidates}")

        for _ in range(10 if not tile_mode else 5):
            logger.info(f"初始向上滑动...")
            context.run_action(
                "UtilsSwipe",
                pipeline_override={
                    "UtilsSwipe": {
                        "begin":[816,120,37,26],
                        "end":[839,551,37,25],
                        "end_hold": 0
                        }
                    }
                )

        i = 0
        while i < 30 and not tile_mode:
            logger.info(f"[DEBUG] ========== 主循环A 迭代第 {i} 次 ==========")
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            get_quest = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "pre_wait_freeze":{
                            "time": 1000,
                            "target": [0, 0, 1080, 720],
                            "threshold": 0.999
                        },
                        "recognition": {
                            "param": {
                                "roi": [494,3,779,671],
                                "duration": 200,
                                "expected": folder_name,
                                "order_by": "Vertical"
                            }
                        }
                    }
                }
            )
            logger.info(f"OCR识别完成")
            if get_quest.filtered_results:
                logger.info(f"识别到的任务:{get_quest.filtered_results}")
            else:
                logger.info(f"未识别到任何任务")
            
            if get_quest.filtered_results: 
                found = False
                for res in get_quest.filtered_results:
                    logger.info(f"检查难度匹配: OCR结果='{res.text}' vs 难度候选={difficulty_candidates}")
                    # OCR may mix full-width and half-width brackets in one result.
                    normalized_text = normalize_brackets(res.text)
                    result_text_candidates = (
                        normalized_text
                        if isinstance(normalized_text, list)
                        else [normalized_text]
                    )
                    if any(
                        d in text
                        for text in result_text_candidates
                        for d in difficulty_candidates
                    ):
                        logger.info(f"匹配")
                        context.run_action(
                            "UtilsClick",
                            res.box,
                            pipeline_override={
                                "UtilsClick": {
                                    "action": {
                                        "param": {
                                            "target": res.box
                                        }
                                    }
                                }
                            }
                        )
                        logger.info(f"成功选择任务")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        return True
                    else:
                        logger.info(f"不匹配")
                
                # for 循环结束，所有结果都不匹配
                logger.info(f"当前屏幕的所有结果都不匹配")
                
                # 分组标题比子关卡向左缩进；标题在底部时先滚动会把它移出屏幕。
                if (
                    len(get_quest.filtered_results) == 1
                    and get_quest.filtered_results[0].box[0] <= 700
                ):
                    header = get_quest.filtered_results[0]
                    result_to_expand = header

                    # 标题靠近底部时，先确认子关卡是否已经展开但在屏幕外。
                    if header.box[1] >= 450:
                        logger.info(f"分组标题位于底部，先上滑确认展开状态: {header}")
                        context.run_action(
                            "UtilsSwipe",
                            pipeline_override={
                                "UtilsSwipe": {
                                    "begin": [933, 603, 24, 18],
                                    "end": [927, 460, 30, 24]
                                }
                            }
                        )
                        probed_quest = self._recognize_quests(context, folder_name)
                        if probed_quest.filtered_results:
                            for res in probed_quest.filtered_results:
                                normalized_text = normalize_brackets(res.text)
                                result_text_candidates = (
                                    normalized_text
                                    if isinstance(normalized_text, list)
                                    else [normalized_text]
                                )
                                if any(
                                    d in text
                                    for text in result_text_candidates
                                    for d in difficulty_candidates
                                ):
                                    logger.info(f"上滑探测发现目标难度，直接选择: {res}")
                                    context.run_action(
                                        "UtilsClick",
                                        res.box,
                                        pipeline_override={
                                            "UtilsClick": {
                                                "action": {
                                                    "param": {
                                                        "target": res.box
                                                    }
                                                }
                                            }
                                        }
                                    )
                                    logger.info(f"成功选择任务")
                                    timeout_mgr.stop_monitoring(argv.node_name)
                                    return True

                            if not (
                                len(probed_quest.filtered_results) == 1
                                and probed_quest.filtered_results[0].box[0] <= 700
                            ):
                                logger.info(f"上滑探测发现子关卡，保留当前展开状态")
                                get_quest = probed_quest
                                result_to_expand = None
                            else:
                                result_to_expand = probed_quest.filtered_results[0]
                        else:
                            logger.info(f"上滑探测未识别到结果，暂不点击标题")
                            result_to_expand = None

                    if result_to_expand is not None:
                        logger.info(f"仅识别到折叠分组标题，点击展开: {result_to_expand}")
                        context.run_action(
                            "UtilsClick",
                            result_to_expand.box,
                            pipeline_override={
                                "UtilsClick": {
                                    "action": {
                                        "param": {
                                            "target": result_to_expand.box
                                        }
                                    }
                                }
                            }
                        )
                        logger.info(f"已展开分组，返回重新识别...")

                # 检查是否只识别了1个子关卡（可能是任务被关闭了）
                elif len(get_quest.filtered_results) == 1:
                    logger.info(f"仅识别1个子关卡，判断是否任务被关闭...")
                    # 先向下滑动看看能否打开任务
                    context.run_action(
                        "UtilsSwipe",
                        pipeline_override={
                            "UtilsSwipe": {
                                "begin":[927,460,30,24],
                                "end":[933,603,24,18],
                            }
                        }
                    )
                    context.tasker.controller.post_screencap().wait()
                    current_image = context.tasker.controller.cached_image
                    get_quest = context.run_recognition(
                        "UtilsOCR",
                        current_image,
                        pipeline_override={
                            "UtilsOCR": {
                                "pre_wait_freeze": {
                                    "time": 1000,
                                    "target": [0, 0, 1080, 720],
                                    "threshold": 0.999
                                },
                                "recognition": {
                                    "param": {
                                        "roi": [494,3,779,671],
                                        "expected": folder_name,
                                        "order_by": "Vertical"
                                    }
                                }
                            }
                        }
                    )
                    logger.info(f"向下滑动后识别中")
                    if len(get_quest.filtered_results) == 1:
                        logger.info(f"滑动后仍是1个结果，任务确实是关闭的，点击展开...")
                        for res in get_quest.filtered_results:
                            context.run_action(
                                "UtilsClick",
                                res.box,
                                pipeline_override={
                                    "UtilsClick": {
                                        "action": {
                                            "param": {
                                                "target": res.box
                                            }
                                        }
                                    }
                                }
                            )
                        logger.info(f"已点击展开，返回重新识别...")
                    else:
                        logger.info(f"滑动后结果数增加，说明任务已展开或找到了新任务")
                else:
                    logger.info(f"识别到多个结果但都不匹配，先向上滑动查找目标...")
                    self.last_len = len(get_quest.filtered_results)
                    
                    # 向上滑动
                    context.run_action(
                        "UtilsSwipe",
                        pipeline_override={
                            "UtilsSwipe": {
                                "begin":[933,603,24,18],
                                "end":[927,460,30,24],
                            }
                        }
                    )
                    context.tasker.controller.post_screencap().wait()
                    current_image = context.tasker.controller.cached_image
                    get_quest = context.run_recognition(
                        "UtilsOCR",
                        current_image,
                        pipeline_override={
                            "UtilsOCR": {
                                "pre_wait_freeze": {
                                    "time": 1000,
                                    "target": [0, 0, 1080, 720],
                                    "threshold": 0.999
                                },
                                "recognition": {
                                    "param": {
                                        "roi": [494,3,779,671],
                                        "expected": folder_name,
                                        "order_by": "Vertical"
                                    }
                                }
                            }
                        }
                    )
                    logger.info(f"向上滑动后识别中")
                    
                    # 判断目标是否已过
                    if self.last_len > len(get_quest.filtered_results):
                        logger.info(f"结果数减少，说明目标已经过了，向下返回...")
                        context.run_action(
                            "UtilsSwipe",
                            pipeline_override={
                                "UtilsSwipe": {
                                    "begin":[840,47,40,23],
                                    "end":[832,327,59,35],
                                }
                            }
                        )
                
                # 继续滑动
                logger.info(f"向下滑动继续查找...")
                context.run_action(
                    "UtilsSwipe",
                    pipeline_override={
                        "UtilsSwipe" : {
                            "begin":[839,551,37,25],
                            "end":[816,120,37,26],
                            }
                        }
                    )
            else:
                # 未识别到任何任务
                logger.info(f"未识别到任何任务，向下滑动...")
                context.run_action(
                    "UtilsSwipe",
                    pipeline_override={
                        "UtilsSwipe": {
                            "begin":[832,327,59,35],
                            "end":[840,47,40,23],
                            }
                        }
                    )

            i += 1

        while i < 30 and tile_mode:
            print(f"\n[DEBUG] ========== 主循环B 迭代第 {i} 次 ==========")
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            get_quest = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "pre_wait_freeze":{
                            "time": 1000,
                            "target": [0, 0, 1080, 720],
                            "threshold": 0.999
                        },
                        "recognition": {
                            "param": {
                                "roi": [494,3,779,671],
                                "duration": 200,
                                "expected": folder_name,
                                "order_by": "Vertical"
                            }
                        }
                    }
                }
            )

            if get_quest.best_result: 
                context.run_action(
                    "UtilsClick",
                    get_quest.best_result.box,
                    pipeline_override={
                        "UtilsClick": {
                            "action": {
                                "param": {
                                    "target": get_quest.best_result.box
                                }
                            }
                        }
                    }
                )
                logger.info(f"成功选择任务")
                timeout_mgr.stop_monitoring(argv.node_name)
                logger.info(f"========== QuestSelect 执行成功 ==========")
                return True
            else:
                logger.info(f"未识别到任何任务")
                context.run_action(
                    "UtilsSwipe",
                    pipeline_override={
                        "UtilsSwipe": {
                            "begin":[796,611,20,20],
                            "end":[796,66,20,20]
                        }
                    }
                )
            i += 1


        logger.info(f"========== 主循环已执行30次，任务失败 ==========")
        timeout_mgr.stop_monitoring(argv.node_name)
        return False
