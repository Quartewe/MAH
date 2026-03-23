from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import time
import json
from utils import data_io, timeout_mgr, proj_path


def normalize_brackets(data):
    """
    将文本或列表转换为包含中英文括号两种版本的列表
    
    例如:
    - "赚取金币的打工（3）" → ["赚取金币的打工（3）", "赚取金币的打工(3)"]
    - ["赚取金币的打工（3）", "副本"] → ["赚取金币的打工（3）", "赚取金币的打工(3)", "副本"]
    - "赚取金币的打工" → ["赚取金币的打工"]
    """
    # 如果输入本身就是列表，对每个元素处理后合并
    if isinstance(data, list):
        result = []
        for item in data:
            result.extend(normalize_brackets(item))
        return list(set(result))  # 去重
    
    # 输入是字符串的情况
    text = str(data)
    # 中文括号 → 英文括号
    english_version = text.replace("（", "(").replace("）", ")")
    # 英文括号 → 中文括号
    chinese_version = text.replace("(", "（").replace(")", "）")
    
    # 返回列表（去重）
    versions = {text, english_version, chinese_version}
    return list(versions)


@AgentServer.custom_action("QuestSelect")
class QuestSelect(CustomAction):
    def __init__(self):
        super().__init__()
        self.last_len = 0

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):    
            return False
        
        param = json.loads(argv.custom_action_param)
        folder_name = normalize_brackets(param.get("name", ""))
        difficulty = normalize_brackets(param.get("difficulty", ""))
        
        print(f"[DEBUG] ========== QuestSelect 开始执行 ==========")
        print(f"[DEBUG] 目标任务名: {folder_name}")
        print(f"[DEBUG] 目标难度: {difficulty}")

        for _ in range(10):
            print(f"[DEBUG] 初始向下滑动...")
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
        while i < 30:
            print(f"\n[DEBUG] ========== 主循环 迭代第 {i} 次 ==========")
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
            print(f"[DEBUG] OCR识别完成，识别结果数: {len(get_quest.filtered_results)}")
            if get_quest.filtered_results:
                print(f"[DEBUG] 识别到的任务:")
                for idx, res in enumerate(get_quest.filtered_results):
                    print(f"[DEBUG]   [{idx}] text={res.text[:50]}, box={res.box}")
            else:
                print(f"[DEBUG] 未识别到任何任务")
            
            if get_quest.filtered_results: 
                found = False
                for res in get_quest.filtered_results:
                    print(f"[DEBUG] 检查难度匹配: '{difficulty}' in '{res.text[:60]}'? ", end="")
                    if difficulty in res.text:
                        print(f"✓ 匹配!")
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
                        print(f"[DEBUG] ✓ 成功选择任务: {res.text[:50]}")
                        timeout_mgr.stop_monitoring(argv.node_name)
                        print(f"[DEBUG] ========== QuestSelect 执行成功 ==========")
                        return True
                    else:
                        print(f"✗ 不匹配")
                
                # for 循环结束，所有结果都不匹配
                print(f"[DEBUG] 当前屏幕的所有结果都不匹配")
                
                # 检查是否只识别了1个结果（可能是任务被关闭了）
                if len(get_quest.filtered_results) == 1:
                    print(f"[DEBUG] 仅识别1个结果，判断是否任务被关闭...")
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
                    print(f"[DEBUG] 向下滑动后识别，结果数: {len(get_quest.filtered_results)}")
                    if len(get_quest.filtered_results) == 1:
                        print(f"[DEBUG] 滑动后仍是1个结果，任务确实是关闭的，点击展开...")
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
                        print(f"[DEBUG] 已点击展开，返回重新识别...")
                    else:
                        print(f"[DEBUG] 滑动后结果数增加，说明任务已展开或找到了新任务")
                else:
                    print(f"[DEBUG] 识别到 {len(get_quest.filtered_results)} 个结果但都不匹配，先向上滑动查找目标...")
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
                    print(f"[DEBUG] 向上滑动后识别，结果数: {len(get_quest.filtered_results)} (之前: {self.last_len})")
                    
                    # 判断目标是否已过
                    if self.last_len > len(get_quest.filtered_results):
                        print(f"[DEBUG] 结果数减少，说明目标已经过了，向下返回...")
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
                print(f"[DEBUG] 向下滑动继续查找...")
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
                print(f"[DEBUG] 未识别到任何任务，向下滑动...")
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

        print(f"[DEBUG] ========== 主循环已执行30次，任务失败 ==========")
        timeout_mgr.stop_monitoring(argv.node_name)
        return False