from pathlib import Path
import json
import time
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
CHAR_FILE = "data/characters.json"


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
