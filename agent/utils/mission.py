import re

from .data_io import IOUtils


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
                        item.box[0] - x in range(0, cls.COMPELETED_X_RANGE)
                        and y - item.box[1] in range(0, cls.COMPELETED_Y_RANGE)
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
                        item.box[0] - x in range(0, cls.NUM_X_RANGE)
                        and item.box[1] - y in range(0, cls.NUM_Y_RANGE)
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

        return True


mission_mgr = MissionUtils
