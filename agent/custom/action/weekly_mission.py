from maa.custom_recognition import CustomRecognition
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
from utils import data_io, timeout_mgr, act_mgr, info_share, proj_path
from copy import deepcopy
import re
import time

# TODO: 支持多语言
@AgentServer.custom_action("WeeklyMission")
class WeeklyMission(CustomAction):
    def __init__(self):
        super().__init__()
        self.NUM_X_RANGE = 200
        self.NUM_Y_RANGE = 56
        self.COMPELETED_X_RANGE = 300
        self.COMPELETED_Y_RANGE = 60
        self.MISSION_ROI = [516,172,586,450]
        self.CN_MISSION = {
                "显示支援者组队画面": {"current": 0, "target": 1, "completed": False},
                "完成攻略3次地城": {"current": 0, "target": 3, "completed": False},
                "累计消耗100点体力": {"current": 100, "target": 100, "completed": False},
                "累计消耗300点体力": {"current": 0, "target": 300, "completed": False},
                "累计消耗450点体力": {"current": 0, "target": 450, "completed": False},
                "累计打倒60个敌人": {"current": 0, "target": 60, "completed": False},
                "累计打倒100个敌人": {"current": 0, "target": 100, "completed": False},
                "完成5次任务": {"current": 0, "target": 5, "completed": False},
                "完成10次任务": {"current": 0, "target": 10, "completed": False},
                "完成每周任务9个": {"current": 0, "target": 9, "completed": False}
        }
        self.JP_MISSION = {
                "サポート編成画面を表示する": {"current": 0, "target": 1, "completed": False},
                "ダンジョンを3回クリアする": {"current": 0, "target": 3, "completed": False},
                "スタミナを累計100消費する": {"current": 100, "target": 100, "completed": False},
                "スタミナを累計300消費する": {"current": 0, "target": 300, "completed": False},
                "スタミナを累計450消費する": {"current": 0, "target": 450, "completed": False},
                "エネミーを累計60体倒す": {"current": 0, "target": 60, "completed": False},
                "エネミーを累計100体倒す": {"current": 0, "target": 100, "completed": False},
                "クエストを5回クリアする": {"current": 0, "target": 5, "completed": False},
                "クエストを10回クリアする": {"current": 0, "target": 10, "completed": False},
                "ウィークリーミッションを9個クリアする":{"current": 0, "target": 9, "completed": False}
        }
        self.TW_MISSION = {
            "顯示協助者編組畫面": {"current": 0, "target": 1, "completed": False},
            "完成攻略3次地城": {"current": 0, "target": 3, "completed": False},
            "累計消費100點體力": {"current": 100, "target": 100, "completed": False},
            "累計消費300點體力": {"current": 0, "target": 300, "completed": False},
            "累計消費450點體力": {"current": 0, "target": 450, "completed": False},
            "累計打倒60個敵人": {"current": 0, "target": 60, "completed": False},
            "累計打倒100個敵人": {"current": 0, "target": 100, "completed": False},
            "完成5次任務": {"current": 0, "target": 5, "completed": False},
            "完成10次任務": {"current": 0, "target": 10, "completed": False},
            "完成每周任務9個": {"current": 0, "target": 9, "completed": False}
        }
        self.EN_MISSION = {
            "Display the Change Support Member screen.": {"current": 0, "target": 1, "completed": False},
            "Clear 3 dungeon quests": {"current": 0, "target": 3, "completed": False},
            "Use 100 stamina points": {"current": 100, "target": 100, "completed": False},
            "Use 300 stamina points": {"current": 0, "target": 300, "completed": False},
            "Use 450 stamina points": {"current": 0, "target": 450, "completed": False},
            "Defeat 60 enemies": {"current": 0, "target": 60, "completed": False},
            "Defeat 100 enemies": {"current": 0, "target": 100, "completed": False},
            "Clear 5 quests": {"current": 0, "target": 5, "completed": False},
            "Clear 10 quests": {"current": 0, "target": 10,"completed": False},
            "Clear 9 weekly missions": {"current": 0, "target": 9, "completed": False}
        }
        self.last_fingerprint = []
        self.last_scan_index = -1
        self.last_info_scan_index = -1

    def _catch_mission_data(self, context):
        mission_data = data_io.read_data(proj_path.STATE_FILE)
        if mission_data == {}:
            match act_mgr.detect_lang(context, [481,19,777,613], info_share.IGNORE_LIST):
                case "jp":
                    mission_data = deepcopy(self.JP_MISSION)
                case "cn":
                    mission_data = deepcopy(self.CN_MISSION)
                case "tw":
                    mission_data = deepcopy(self.TW_MISSION)
                case "en":
                    mission_data = deepcopy(self.EN_MISSION)

        while True:
            current_fingerprint = []
            rec_compeleted = False
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            mission_res = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition":{
                            "param":{
                                "roi": self.MISSION_ROI,
                                "order_by": "Vertical"
                            }
                        }
                    }
                }
            )
            print(mission_res.all_results)
            indexed_results = list(enumerate(mission_res.all_results))
            if indexed_results and self.last_scan_index >= 0:
                start_index = (self.last_scan_index + 1) % len(indexed_results)
                scan_results = indexed_results[start_index:] + indexed_results[:start_index]
            else:
                scan_results = indexed_results

            indexed_info_results = list(enumerate(mission_res.filtered_results))
            if indexed_info_results and self.last_info_scan_index >= 0:
                info_start_index = (self.last_info_scan_index + 1) % len(indexed_info_results)
                info_scan_results = indexed_info_results[info_start_index:] + indexed_info_results[:info_start_index]
            else:
                info_scan_results = indexed_info_results

            round_last_scan_index = self.last_scan_index
            round_last_info_scan_index = self.last_info_scan_index
            for mission in mission_data.keys():
                for idx, item in scan_results:
                    if mission in item.text:
                        round_last_scan_index = idx
                        print(f"[DEBUG] 任务 {mission} 匹配到文本: {item.text}")
                        current_fingerprint.append((item.text))
                        for info_idx, info in info_scan_results:
                            if info.text.strip().strip('"').strip("'") in ["進行度", "进行度"]:
                                continue
                            if 0 < item.box[1] - info.box[1] < self.COMPELETED_Y_RANGE and info.text.strip().strip('"').strip("'") == "COMPLETED":
                                mission_data[mission]["completed"] = True
                                mission_data[mission]["current"] = mission_data[mission]["target"]
                                print(f"[DEBUG] 任务 {mission} 已完成")
                                rec_compeleted = True
                                round_last_info_scan_index = info_idx
                                break
                            elif "/" in info.text and info.box[1] - item.box[1] in range(0, self.NUM_Y_RANGE) and info.box[0] - item.box[0] in range(0, self.NUM_X_RANGE):
                                print(f"[DEBUG] 任务 {mission} 匹配到可能的进度文本: {info.text}")     
                                numbers = re.findall(r'\d+', info.text)
                                if len(numbers) < 2:
                                    continue
                                current, target = int(numbers[0]), int(numbers[1])
                                mission_data[mission]["current"] = current
                                mission_data[mission]["target"] = target
                                if current >= target:
                                    mission_data[mission]["completed"] = True
                                print(f"[DEBUG] 任务 {mission} 当前进度: {current}/{target}")
                                rec_compeleted = True
                                round_last_info_scan_index = info_idx
                                break
                        break
            self.last_scan_index = round_last_scan_index
            self.last_info_scan_index = round_last_info_scan_index
            if rec_compeleted:
                context.run_action(
                    "UtilsSwipe",
                    pipeline_override={
                        "UtilsSwipe": {
                            "action": {
                                "param": {
                                    "begin": [770, 577, 50, 10],
                                    "end": [770,93,50,10],
                                    "duration": 500,
                                    "end_hold": 500
                                }
                            }
                        }
                    }
                )
            
            time.sleep(1)
            if current_fingerprint != self.last_fingerprint:
                print("[DEBUG] last_fingerprint:", self.last_fingerprint)
                print("[DEBUG] current_fingerprint:", current_fingerprint)
                self.last_fingerprint = current_fingerprint
            else:
                print("[DEBUG] OCR结果与上次相同，认为已经读取完成")
                return mission_data

    def _reset_mission_data(self, context):
        match act_mgr.detect_lang(context, [481,19,777,613], info_share.IGNORE_LIST):
            case "jp":
                mission_data = deepcopy(self.JP_MISSION)
            case "cn":
                mission_data = deepcopy(self.CN_MISSION)
            case "tw":
                mission_data = deepcopy(self.TW_MISSION)
            case "en":
                mission_data = deepcopy(self.EN_MISSION)
        return mission_data

    def _set_to_completed(self, context):
        match act_mgr.detect_lang(context, [481,19,777,613], info_share.IGNORE_LIST):
            case "jp":
                mission_data = deepcopy(self.JP_MISSION)
            case "cn":
                mission_data = deepcopy(self.CN_MISSION)
            case "tw":
                mission_data = deepcopy(self.TW_MISSION)
            case "en":
                mission_data = deepcopy(self.EN_MISSION)
        for mission in mission_data.keys():
            mission_data[mission]["completed"] = True
            mission_data[mission]["current"] = mission_data[mission]["target"]
        return mission_data

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):    
            return False

        success = True
        # 选择任务
        if argv.node_name == "CheckWeeklyMissions.Record":
            if data_io.write_data(self._catch_mission_data(context), proj_path.STATE_FILE):
                timeout_mgr.stop_monitoring(argv.node_name)
                return True
            else:
                print("[DEBUG] Failed to write mission data to file")
                return False
                
        elif argv.node_name == "CheckWeeklyMissions.AllCompleted":
            success = data_io.write_data(self._set_to_completed(context), proj_path.STATE_FILE)
            timeout_mgr.stop_monitoring(argv.node_name)
            return success

        # 如果是周一且是入口节点，重置任务数据
        if "Entry" in argv.node_name:
            data_io.clear_folder(proj_path.ON_ERROR_DIR)
            if datetime.now().weekday() == 0:
                success = data_io.write_data(self._reset_mission_data(context), proj_path.STATE_FILE)
            timeout_mgr.stop_monitoring(argv.node_name)
            return True
        
