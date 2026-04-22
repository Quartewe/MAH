from maa.custom_recognition import CustomRecognition
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from datetime import datetime
from utils import data_io, timeout_mgr, act_mgr, info_share, proj_path
from copy import deepcopy
import re
import time

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

    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        if text is None:
            return ""
        return str(text).strip().strip('"').strip("'").replace(" ", "")

    def _extract_progress(self, text: str):
        normalized = self._normalize_ocr_text(text).replace("／", "/")
        if "/" not in normalized:
            return None
        numbers = re.findall(r"\d+", normalized)
        if len(numbers) < 2:
            return None
        return int(numbers[0]), int(numbers[1])

    def _pick_mission_info(self, mission_item, ocr_results):
        mission_x, mission_y = mission_item.box[0], mission_item.box[1]
        best_progress = None
        best_cost = None

        for info in ocr_results:
            if info is mission_item:
                continue

            info_text = self._normalize_ocr_text(info.text)
            if not info_text:
                continue
            if info_text in ["進行度", "进行度"]:
                continue
            if "期限" in info_text or "小时" in info_text or "分鐘" in info_text or "分钟" in info_text:
                continue

            dx = info.box[0] - mission_x
            dy = info.box[1] - mission_y
            if not (50 <= dx <= 420 and -20 <= dy <= 140):
                continue

            if info_text.upper() == "COMPLETED":
                return "completed", None

            progress = self._extract_progress(info_text)
            if not progress:
                continue

            cost = abs(dx - 180) + abs(dy - 55) * 4
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_progress = progress

        if best_progress is not None:
            return "progress", best_progress
        return None, None

    def _catch_mission_data(self, context):
        mission_data = data_io.read_data(proj_path.STATE_FILE)

        if mission_data == {}:
            print("[DEBUG] 未找到已有任务数据，正在检测语言并初始化任务数据")
            match act_mgr.detect_lang(context, [481,19,777,613], info_share.IGNORE_LIST):
                case "jp":
                    mission_data = deepcopy(self.JP_MISSION)
                case "cn":
                    mission_data = deepcopy(self.CN_MISSION)
                case "tw":
                    mission_data = deepcopy(self.TW_MISSION)
                case "en":
                    mission_data = deepcopy(self.EN_MISSION)

        state_keys = mission_data.keys() if mission_data else None
        state_lang = act_mgr.detect_lang(context, [0,0,0,0], info_share.IGNORE_LIST, compare_list=state_keys)
        if state_lang != info_share.current_lang:
            print(f"[WARNING] 检测语言 {state_lang} 与当前语言 {info_share.current_lang} 不一致，正在重置任务数据")
            match state_lang:
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
            should_swipe = False
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
            ocr_results = list(mission_res.all_results)
            print(ocr_results)

            for mission in mission_data.keys():
                matched_items = [res for res in ocr_results if mission in self._normalize_ocr_text(res.text)]
                if not matched_items:
                    continue

                mission_item = max(matched_items, key=lambda item: item.score)
                print(f"[DEBUG] 任务 {mission} 匹配到文本: {mission_item.text}")
                current_fingerprint.append(mission)
                should_swipe = True

                info_type, progress = self._pick_mission_info(mission_item, ocr_results)
                if info_type == "completed":
                    mission_data[mission]["completed"] = True
                    mission_data[mission]["current"] = mission_data[mission]["target"]
                    print(f"[DEBUG] 任务 {mission} 已完成")
                elif info_type == "progress" and progress is not None:
                    current, target = progress
                    mission_data[mission]["current"] = current
                    mission_data[mission]["target"] = target
                    mission_data[mission]["completed"] = current >= target
                    print(f"[DEBUG] 任务 {mission} 当前进度: {current}/{target}")

            if should_swipe:
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
                print("[DEBUG] 上一次指纹:", self.last_fingerprint)
                print("[DEBUG] 当前指纹:", current_fingerprint)
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
                print("[DEBUG] 写入任务数据到文件失败")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
                
        elif argv.node_name == "CheckWeeklyMissions.AllCompleted":
            success = data_io.write_data(self._set_to_completed(context), proj_path.STATE_FILE)
            timeout_mgr.stop_monitoring(argv.node_name)
            return success

        timeout_mgr.stop_monitoring(argv.node_name)
        return True
        
