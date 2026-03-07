from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
import numpy
import json
import time
import re
import os
import copy

DEFAULT_STATE = {
    "missions": {
        "显示支援者组队画面": {"current": 0, "target": 1, "completed": False},
        "完成攻略3次地城": {"current": 0, "target": 3, "completed": False},
        "累计消耗100点体力": {"current": 100, "target": 100, "completed": False},
        "累计消耗300点体力": {"current": 0, "target": 300, "completed": False},
        "累计消耗450点体力": {"current": 0, "target": 450, "completed": False},
        "累计打倒60个敌人": {"current": 0, "target": 60, "completed": False},
        "累计打倒100个敌人": {"current": 0, "target": 100, "completed": False},
        "完成5次任务": {"current": 0, "target": 5, "completed": False},
        "完成10次任务": {"current": 0, "target": 10, "completed": False},
        "完成每周任务9个": {"current": 0, "target": 9, "completed": False},
        "if_all_completed": False,
    },
    "resources": {
        "AP": {"value": 0, "upper_limit": 0, "last_updated": 0},
        "DP": {"value": 0, "upper_limit": 3, "last_updated": 0},
        "Stone": 0,
        "RF": 0,
    },
}

STATE_FILE = "data/state.json"
CHAR_FILE= "data/characters.json"

class MatchUtils:
    @staticmethod
    def fuzzy_match(text, keywords, threshold=0.8):
        # 处理关键词为字符串或列表的情况
        if isinstance(keywords, str):
            keywords = [keywords]
        for keyword in keywords:
            ratio = SequenceMatcher(None, text, keyword).ratio()
            if ratio >= threshold:
                return True
        return False

match_mgr = MatchUtils

class IOUtils:
    @staticmethod   
    def read_data(file_path: str = None) -> dict:
        """
        读取数据文件
        file_path: 文件路径，如果为None则使用默认的STATE_FILE
        """
        if file_path is None:
            file_path = STATE_FILE
            
        try:
            if not os.path.exists("data"):
                os.makedirs("data")
                # debug
                print("[DEBUG] data folder created")
                #

            if not os.path.exists(file_path):
                # debug
                print(f"[DEBUG] file not found: {file_path}, creating default file")
                #
                # 创建父目录
                os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
                # 创建文件并写入默认数据
                default_data = copy.deepcopy(DEFAULT_STATE)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, ensure_ascii=False, indent=4)
                return default_data

            with open(file_path, "r", encoding="utf-8") as f:
                # debug
                print(f"[DEBUG] reading file: {file_path}...")
                #
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # debug
            print(f"[DEBUG] file {file_path} is corrupted, now will create it")
            #
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            default_data = copy.deepcopy(DEFAULT_STATE)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_data, f, ensure_ascii=False, indent=4)
            # 重新读取文件
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    def write_data(data: dict, file_path: str = None):
        """
        写入数据文件
        file_path: 文件路径，如果为None则使用默认的STATE_FILE
        """
        if file_path is None:
            file_path = STATE_FILE
            
        with open(file_path, "w", encoding="utf-8") as f:
            # debug
            print(f"[DEBUG] writing file: {file_path}...")
            #
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def reset_data(nodename: str):
        state = IOUtils.read_data()

        match nodename:
            case name if "Missions" in name or "Startup" in name:
                state["missions"] = copy.deepcopy(DEFAULT_STATE["missions"])
                # debug
                print("[DEBUG] missions reset")
                #
            case name if "Resource" in name:
                state["resources"] = copy.deepcopy(DEFAULT_STATE["resources"])
                # 记录重置时的时间戳
                state["resources"]["AP"]["last_updated"] = time.time()
                state["resources"]["DP"]["last_updated"] = time.time()
                # debug
                print("[DEBUG] resources reset, last_updated set to now")
                #

        IOUtils.write_data(state)

    @staticmethod
    def set_to_completed():
        state = IOUtils.read_data()
        for mission in state["missions"]:
            if isinstance(state["missions"][mission], dict):
                state["missions"][mission]["completed"] = True
                # debug
                print(f"[DEBUG] mission {mission} set to completed")
                #
                state["missions"][mission]["current"] = state["missions"][mission][
                    "target"
                ]
                # debug
                print(
                    f"mission {mission} value set to {state['missions'][mission]['current']}"
                )
                #
        state["missions"]["if_all_completed"] = True
        # debug
        print("[DEBUG] if_all_completed set to True")
        #
        IOUtils.write_data(state)
        return True

    # 格式化OCR内容并输出到文件
    @staticmethod
    def organize_ocr_log(node_name: str, _reco_detail):
        raw_log = str(_reco_detail)
        organized_log = ""
        i = 0
        depth = 0
        if ", raw_detail" in raw_log:
            raw_log = raw_log.split(", raw_detail")[0]
        while i < len(raw_log):
            char = raw_log[i]
            # 进入括号：深度+1，针对顶层列表执行内部换行缩进
            if char in "([":# debug
                depth += 1
                if depth <= 2:
                    organized_log += char + "\n" + "      " * depth
                else:
                    organized_log += char
            # 退出括号：深度-1，回位换行
            elif char in ")]":# debug
                if depth <= 2:
                    organized_log += "\n" + "      " * (depth - 1) + char
                else:
                    organized_log += char
                depth -= 1
            # 逗号分割：仅在顶层深度（1或2）处触发分割换行
            elif char == "," and depth <= 2:
                organized_log += ",\n" + "      " * depth
            else:
                organized_log += char

            # 修复 Bug：先添加字符，再独立判断是否跳过紧随其后的空格
            if i + 1 < len(raw_log) and raw_log[i + 1] == " ":
                i += 1
            i += 1

        # debug
        print("[DEBUG] already organized ocr log")
        #
        if not os.path.exists("debug"):
            os.makedirs("debug")
            # debug
            print("[DEBUG] debug folder not exist, now creating debug folder...")
            #

        with open("debug/ocr_detail.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime(time.time())))
            f.write("\n")
            f.write(node_name)
            f.write(":\n")
            f.write(organized_log.strip())
            f.write("\n")
            # debug
            print("[DEBUG] ocr_detail.log written")
            #

        return organized_log

data_io = IOUtils

class ResourceUtils:
    AP_RECOVERY_INTERVAL = 480  # 8分钟 480秒
    CN_RESET_HOUR = 3  # CN凌晨3点刷新

    @classmethod
    def get_estimated_resources(cls) -> dict:
        state = IOUtils.read_data()
        res = state.get("resources", DEFAULT_STATE["resources"])
        now_ts = time.time()

        estimated = {}

        # 体力
        print("[DEBUG] now calculating AP data...")
        ap = res.get("AP", {"value": 0, "upper_limit": 0, "last_updated": 0})
        if ap["last_updated"] == 0 or cls.AP_RECOVERY_INTERVAL <= 0:
            estimated["AP"] = ap["value"]
        else:
            passed_time = now_ts - ap["last_updated"]
            recovered = int(passed_time // cls.AP_RECOVERY_INTERVAL)
            estimated["AP"] = min(ap["value"] + recovered, ap.get("upper_limit", 0))
        # debug
        print("[DEBUG] AP data calculated")
        #

        # DP
        print("[DEBUG] now calculating DP data...")
        dp = res.get("DP", {"value": 0, "upper_limit": 3, "last_updated": 0})
        if dp["last_updated"] == 0:
            estimated["DP"] = dp["value"]
        else:
            last_dt = datetime.fromtimestamp(dp["last_updated"]) - timedelta(
                hours=cls.CN_RESET_HOUR
            )
            now_dt = datetime.fromtimestamp(now_ts) - timedelta(hours=cls.CN_RESET_HOUR)
            days_passed = (now_dt.date() - last_dt.date()).days

            estimated["DP"] = min(
                dp["value"] + max(0, days_passed), dp.get("upper_limit", 3)
            )
        # debug
        print("[DEBUG] DP data calculated")
        #

        # 石头虹碎
        estimated["Stone"] = res.get("Stone", 0)
        estimated["RF"] = res.get("RF", 0)
        # debug
        print("[DEBUG] Stone and RF data already recorded")
        #
        return estimated

resource_mgr = ResourceUtils

class MissionUtils:
    NUM_X_RANGE = 200
    NUM_Y_RANGE = 56
    COMPELETED_X_RANGE = 550
    COMPELETED_Y_RANGE = 80
    last_fingerprint = ""
    ALL_MISSIONS = [
        "显示支援者组队画面",
        "完成攻略3次地城",        
        "累计消耗100点体力",
        "累计消耗300点体力",
        "累计消耗450点体力",
        "累计打倒60个敌人",
        "累计打倒100个敌人",
        "完成每周任务9个",
        "完成5次任务",
        "完成10次任务",
    ]

    @classmethod
    def cut_number(cls, f_result: list, mission_name: str):
        situation = False
        cut_nums = []
        # debug
        print("[DEBUG] Start cutting...")
        #
        # 匹配任务->获取目标值
        if mission_name in cls.ALL_MISSIONS:
            # 找到当前任务在结果中的位置（锚点）
            anchor = None
            for item in f_result:
                if mission_name in item.text:
                    anchor = item
                    break
            
            if anchor:
                x, y = anchor.box[0], anchor.box[1]
                
                # 第一轮：优先检查是否已完成
                for item in f_result:
                    # 判断是否完成
                    if (
                        # 右上
                        0 <= (item.box[0] - x) <= cls.COMPELETED_X_RANGE
                        and 0 <= (y - item.box[1]) <= cls.COMPELETED_Y_RANGE
                        and item.text.strip() == "COMPLETED"
                    ):
                        # debug
                        print(f"[DEBUG] {mission_name} is already COMPLETED")
                        #
                        cut_nums = []
                        situation = True
                        return cut_nums, situation

                # 第二轮：如果未完成，尝试获取数字
                for item in f_result:
                    # 若未完成获取数字
                    if (
                        # 右下
                        0 <= (item.box[0] - x) <= cls.NUM_X_RANGE
                        and 0 <= (item.box[1] - y) <= cls.NUM_Y_RANGE
                    ):
                        # 切数字
                        temp_nums = re.findall(r"(\d+)", item.text.strip())
                        if temp_nums and len(temp_nums) >= 2:
                            # debug
                            print(f"[DEBUG] {mission_name} is not COMPLETED, caught numbers: {temp_nums}")
                            #
                            cut_nums = temp_nums
                            situation = True
                            break
        
        return cut_nums, situation

    @classmethod
    def catch_task(cls, f_results):
        state = IOUtils.read_data()
        all_missions = state["missions"]
        updated = False
        current_fingerprint = ""

        for mission in cls.ALL_MISSIONS:
            for item in f_results:
                if mission in item.text:
                    # 生成当前屏的唯一指纹（任务名）
                    current_fingerprint += f"{mission}|"                   
                    nums, situation = cls.cut_number(f_results, mission)
                    if situation and nums:
                        all_missions[mission]["current"] = int(nums[0].strip())
                        all_missions[mission]["target"] = int(nums[1].strip())
                        all_missions[mission]["completed"] = int(nums[0].strip()) >= int(nums[1].strip())
                        updated = True
                        break
                    elif situation:
                        all_missions[mission]["current"] = all_missions[mission]["target"]
                        all_missions[mission]["completed"] = True
                        updated = True
                        break
        
        # debug
        print(f"[DEBUG] Mission in this page: {current_fingerprint}")
        print(f"[DEBUG] Mission in last page: {cls.last_fingerprint}")
        #

        # 判断指纹是否重复
        if current_fingerprint and current_fingerprint == cls.last_fingerprint:
            # debug
            print("Same fingerprint, already at bottom")
            #
            return False

        cls.last_fingerprint = current_fingerprint

        # 只有在抓到数据时才保存文件
        if updated:
            state["missions"] = all_missions
            # debug
            print("data have already saved")
            #
            IOUtils.write_data(state)

mission_mgr = MissionUtils

class ActUtils:
    DEFAULT_BEGIN = [330, 530, 10, 10]
    DEFAULT_END = [330, 15, 10, 10]

    @staticmethod
    def merge_res_dicts(existing: dict, new: dict) -> dict:
        """
        合并字典：将 new 中的 res_* 键重新编号后追加到 existing
        
        Args:
            existing: 已有的结果字典，可能包含 res_0, res_1 等
            new:      新的结果字典，包含 res_0, res_1 等
            
        Returns:
            合并后的字典，new 的键被重编号为 res_2, res_3 等
        """
        if not existing:
            return new
        if not new:
            return existing
        
        # 找出 existing 中已有的最大 res 索引
        max_idx = -1
        for key in existing.keys():
            if isinstance(key, str) and key.startswith("res_"):
                try:
                    idx = int(key.split("_")[1])
                    max_idx = max(max_idx, idx)
                except (ValueError, IndexError):
                    pass
        
        # new_start_idx 是新编号的起始位置
        new_start_idx = max_idx + 1
        
        # 遍历 new 中的 res_* 键，重新编号后加入 existing
        merged = {**existing}  # 拷贝 existing
        for key, val in new.items():
            if isinstance(key, str) and key.startswith("res_"):
                try:
                    old_idx = int(key.split("_")[1])
                    new_key = f"res_{new_start_idx + old_idx}"
                    merged[new_key] = val
                except (ValueError, IndexError):
                    pass  # 跳过无效的键
        
        return merged

    @classmethod
    def swipe(cls, context, begin_box: list = DEFAULT_BEGIN, end_box: list = DEFAULT_END, 
              duration: float = 0.5, contact: int = 0, pressure: int = 128,
              cp1=None, cp2=None, timing: str = "ease_out_quad"):
        """
        # 平滑贝塞尔滑动（空间+时间曲线）
        
        Args:
            # context: MaaFramework 上下文
            # begin_box: 起始范围 [x, y, width, height]
            ## default(all_page): [330, 530, 10, 10]
            # end_box: 结束范围 [x, y, width, height]
            ## default(all_page): [330, 15, 10, 10]
            ### 默认划过三个单位块
            # duration: 滑动时长（秒）
            # contact: 接触点号（0=第一手指/左键）
            # pressure: 压力值（0-255）
            # cp1, cp2: 贝塞尔控制点（可选，None 则自动计算）
            # timing: 时间缓动函数 ('linear', 'ease_out_quad', 'ease_in_out_sine' 等)
            ## linear(t):t 均匀速度，线性运动
            ## ease_in_quad(t): 起始很慢，逐渐加速（加速度）
            ## ease_out_quad(t): 起始很快，逐渐减速（减速度） ⭐常用
            ## ease_in_out_quad(t): 前半段加速，后半段减速，形成 S 形
            ## ease_in_cubic(t): 比 quad 更强的加速效果
            ## ease_out_cubic(t): 比 quad 更强的减速效果
            ## ease_in_out_cubic(t): 更平滑的 S 形     
            ## ease_in_out_sine(t): 正弦波形的缓动，最平滑的 S 形

        Returns:
            bool: 操作是否成功
        """
        import random
        import math
        
        try:
            # 1. 从范围内随机取点
            x1 = begin_box[0] + random.randint(0, int(begin_box[2]))
            y1 = begin_box[1] + random.randint(0, int(begin_box[3]))
            x2 = end_box[0] + random.randint(0, int(end_box[2]))
            y2 = end_box[1] + random.randint(0, int(end_box[3]))
            
            # 2. 自动计算控制点（默认对称上凸）
            if cp1 is None or cp2 is None:
                mid_y = (y1 + y2) / 2 - 50
                cp1 = (x1, mid_y)
                cp2 = (x2, mid_y)
            
            # 3. 用 numpy 计算贝塞尔曲线（空间曲线）
            P = numpy.array([
                [x1, cp1[0], cp2[0], x2],
                [y1, cp1[1], cp2[1], y2]
            ])  # shape (2, 4)
            
            steps = max(10, int(duration * 100))
            t = numpy.linspace(0, 1, steps + 1)
            
            # 伯恩斯坦系数
            mt = 1 - t
            basis = numpy.array([
                mt**3,
                3 * mt**2 * t,
                3 * mt * t**2,
                t**3
            ])  # shape (4, steps+1)
            
            # 计算曲线点
            curve = (P @ basis).T.astype(int)  # shape (steps+1, 2)
            
            # 4. 计算时间间隔（时间缓动） ⭐核心部分
            time_intervals = cls._compute_time_intervals(
                numpy.linspace(0, 1, steps + 1),
                timing,
                duration
            )
            
            # 5. 执行滑动
            x0, y0 = curve[0, 0], curve[0, 1]
            context.controller.post_touch_down(contact, x0, y0, pressure).wait()
            time.sleep(0.05)
            
            for i in range(1, len(curve)):
                x, y = curve[i, 0], curve[i, 1]
                context.controller.post_touch_move(contact, x, y, pressure).wait()
                time.sleep(time_intervals[i])
            
            context.controller.post_touch_up(contact).wait()
            return True
            
        except Exception as e:
            print(f"[Bezier Swipe] 失败: {e}")
            return False
    
    @staticmethod
    def _compute_time_intervals(t_values, timing_func_name: str, total_duration: float) -> list:
        """
        根据时间缓动函数计算每步的时间间隔
        
        Args:
            t_values: 参数 t 的数组 [0, 0.02, 0.04, ..., 1]
            timing_func_name: 缓动函数名（如 'ease_out_quad'）
            total_duration: 总时长（秒）
        
        Returns:
            时间间隔列表（与 t_values 长度相同）
        """
        import math
        
        # 定义所有缓动函数
        def linear(t):
            return t
        
        def ease_in_quad(t):
            return t * t
        
        def ease_out_quad(t):
            return 1 - (1 - t) ** 2
        
        def ease_in_out_quad(t):
            return 2 * t ** 2 if t < 0.5 else -1 + (4 - 2 * t) * t
        
        def ease_in_cubic(t):
            return t ** 3
        
        def ease_out_cubic(t):
            return 1 - (1 - t) ** 3
        
        def ease_in_out_cubic(t):
            return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
        
        def ease_in_out_sine(t):
            return -(math.cos(math.pi * t) - 1) / 2
        
        # 选择缓动函数
        easing_map = {
            'linear': linear,
            'ease_in_quad': ease_in_quad,
            'ease_out_quad': ease_out_quad,
            'ease_in_out_quad': ease_in_out_quad,
            'ease_in_cubic': ease_in_cubic,
            'ease_out_cubic': ease_out_cubic,
            'ease_in_out_cubic': ease_in_out_cubic,
            'ease_in_out_sine': ease_in_out_sine,
        }
        
        easing_fn = easing_map.get(timing_func_name, ease_out_quad)
        
        # 应用缓动到参数空间
        eased_t = numpy.array([easing_fn(t) for t in t_values])
        
        # 计算相邻点之间的时间间隔
        # Δt_eased ∝ Δt_actual
        intervals = numpy.diff(eased_t) * total_duration
        
        # 补充第一个点（通常不用）
        intervals = numpy.concatenate([[0.0], intervals])
        
        return intervals.tolist()
    

act_mgr = ActUtils

class TimeoutUtils:
    _monitoring_tasks = {}
    DEFAULT_TIMEOUT = 300

    @classmethod
    def check_timeout(cls, task_name: str, timeout: int = DEFAULT_TIMEOUT) -> bool:

        now = time.time()
        
        if task_name not in cls._monitoring_tasks:
            cls._monitoring_tasks[task_name] = now
            # debug
            print(f"Start monitoring task: {task_name}, timeout: {timeout}s")
            #
            return False
            
        elapsed = now - cls._monitoring_tasks[task_name]
        if elapsed > timeout:
            # debug
            print(f"Task {task_name}'s Agent Error! Elapsed: {elapsed:.2f}s")
            #
            return True
            
        return False

    @classmethod
    def stop_monitoring(cls, task_name: str):
        """取消任务计时"""
        if task_name in cls._monitoring_tasks:
            del cls._monitoring_tasks[task_name]
            # debug
            print(f"Stopped monitoring task: {task_name}")
            #

timeout_mgr = TimeoutUtils


