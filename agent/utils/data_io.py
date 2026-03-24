from pathlib import Path
import json
import time
import os
import copy
import shutil
from . import proj_path

# 使用统一的路径管理模块
STATE_FILE = proj_path.STATE_FILE
CHAR_FILE = proj_path.CHAR_FILE


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
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump({}, f, ensure_ascii=False, indent=4)
                return {}

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
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=4)
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
        
        return True

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
    
    @staticmethod
    def find_target_files(root_path: Path, target_file: str) -> dict:
        """
        查找目标文件。支持相对路径和绝对路径。
        相对路径相对于项目根目录（data_io.py 所在目录的父目录的父目录）
        """
        output = {}

        if not target_file:
            print(f"[DEBUG] No target file specified for searching.")
            return None

        print(f"[DEBUG] Searching for {target_file} in {root_path}...")
        
        # 检查路径是否存在
        if not root_path.exists():
            print(f"[DEBUG] Search path does not exist: {root_path}")
            return None
            
        files = list(root_path.rglob(target_file))
        print(f"[DEBUG] {files}")
        if len(files) != 1:
            print(f"[DEBUG] Expected 1 file, but found {len(files)}")
            return None
        for file in files:
            # 检查文件是否为空
            if file.stat().st_size == 0:
                print(f"[DEBUG] 找到的文件为空: {file}")
                return None
            try:
                with open(file, "r", encoding="utf-8") as f:
                    output = json.load(f)
            except json.JSONDecodeError as e:
                print(f"[DEBUG] JSON解析失败 {file}: {e}")
                return None
        return output

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

    @staticmethod
    def clear_folder(folder_path: str) -> None:
        folder = Path(folder_path)
        if not folder.exists():
            return  # 路径不存在，直接跳过，不删除
        for item in folder.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()


data_io = IOUtils
