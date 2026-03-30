from collections import Counter
from pathlib import Path
import time
import random
import re
import hanzidentifier
from utils import data_io, match_mgr, proj_path, info_share

class ActUtils:
    DEFAULT_BEGIN = [330, 530, 5, 5]
    DEFAULT_END = [330, 15, 5, 5]
    UI_DATA = data_io.read_data(proj_path.UI_FILE)

    @staticmethod
    def normalize_template_path(path_value):
        if path_value is None:
            return None

        path_str = str(path_value).replace("\\", "/").lstrip("./")
        image_root_rel = proj_path.IMAGE_DIR.relative_to(proj_path.PROJECT_ROOT).as_posix()
        prefix = f"{image_root_rel}/"

        if path_str.startswith(prefix):
            return path_str[len(prefix):]
        return path_str

    @staticmethod
    def if_bottom(lastfingerprint: list, currentfingerprint: list):
        """判断是否还没滑到底部。返回 True 表示还没到底，False 表示到底了（指纹重复）"""
        # 如果当前指纹为空，说明 OCR 没识别到任何内容，视为到底
        if not currentfingerprint:
            return False
        # 上次为空（首次），还没到底
        if not lastfingerprint:
            return True
        # 如果当前指纹中任意元素和上次的重复则认为到底
        for cur in currentfingerprint:
            for las in lastfingerprint:
                if las == cur:
                    return False
        return True

    @staticmethod
    def choose_best(res: dict, limit: dict, keywords: list, mode: str = "best"):
        """
        args:
            res: 识别结果字典，包含多个 res_* 键，每个键对应一个识别结果
            limit: 限制最低数值字典
            keywords: 关键词列表，用于匹配识别结果中的文本, 优先级从左到右
            mode: 选择模式:
                "first": 选择keywords中第一个关键词的最大值
                "best": 优先从满足条件的keywords中选出现最多的结果，如果都不满足则从所有keywords中选出现最多的
        """
        output_all = {}  # 所有keyword对应的best数据
        output_satisfied = {}  # 满足条件的keyword对应的best数据
        check_satisfied = []
        
        # 计算真实的结果数量
        result_count = 0
        for char_name_dict in res.values():
            for char_id_dict in char_name_dict.values():
                result_count += len([k for k in char_id_dict.keys() if k.startswith("res_")])
        print(f"[DEBUG] number of res: {result_count}")

        if isinstance(keywords, str):
            keywords = [keywords]
        
        for keyword in keywords:
            print(f"[DEBUG] Evaluating keyword: {keyword}")
            best = -1
            best_data = None
            best_key = None
            unsatisfied = False
            for char_name_dict in res.values():
                for char_id_dict in char_name_dict.values():
                    for res_key, res_data in char_id_dict.items():
                        if not res_data.get(keyword):
                            continue

                        value = int(res_data.get(keyword))
                        limit_val = int(limit.get(keyword, 0))
                        if value > best:
                            best = value
                            if best < limit_val:
                                unsatisfied = True
                            else:
                                unsatisfied = False
                            best_data = res_data
                            best_key = res_key

            if unsatisfied:
                check_satisfied.append(False)
            else:
                check_satisfied.append(True)
            
            # 无条件保存到output_all
            if best_data:
                output_all[keyword] = best_data
                # 如果满足条件，也保存到output_satisfied
                if check_satisfied[-1]:
                    output_satisfied[keyword] = best_data

        # 优先使用满足条件的，如果都不满足就用全部
        output = output_satisfied if output_satisfied else output_all
        
        if mode == "first":
            most_common_data = output.get(keywords[0], None)
        elif mode == "best":
            # 统计output中哪个 res_data 出现最多
            if output:
                id_counter = Counter(id(v) for v in output.values())
                best_id = id_counter.most_common(1)[0][0]
                most_common_data = next(v for v in output.values() if id(v) == best_id)
            else:
                most_common_data = None
        else:
            most_common_data = None

        # 根据最优数据找到对应的 res_key
        if most_common_data:
            for char_name_dict in res.values():
                for char_id_dict in char_name_dict.values():
                    for res_key, res_data in char_id_dict.items():
                        if res_data is most_common_data:
                            print(f"[DEBUG] Chosen res_key: {res_key}")
                            return res_key
        print(f"[DEBUG] No suitable res_key found")
        return ""
                    
    @staticmethod
    def in_roi(target: list, roi: list):
        """
        判断目标是否在指定区域内
        Args:
            target: 目标坐标 [x, y, width, height]
            roi: 区域坐标 [x, y, width, height]
        Returns:
            bool: 目标是否在区域内
        """
        
        if target[0] > roi[0] and target[1] > roi[1] and target[0] + target[2] <= roi[0] + roi[2] and target[1] + target[3] <= roi[1] + roi[3]:
            return True
        return False

    @staticmethod
    def random_choose(box: list = None):
        """在指定范围内随机选择一个点，范围由box定义，格式为[x, y, width, height]"""
        x1 = int(box[0] + random.randint(0, int(box[2])))
        y1 = int(box[1] + random.randint(0, int(box[3])))
        return x1, y1

    @staticmethod
    def get_list_depth(lst):
        """检测列表的嵌套深度"""
        return 1 + max(map(ActUtils.get_list_depth, lst), default=0) if isinstance(lst, list) else 0

    @staticmethod
    def _run_ocr_and_count_lang(context, roi, max_retries=30, ignore: list = None, compare_list: list = None):
        """执行 OCR 识别并统计语言，返回语言计数字典"""
        jp = cn = tw = en = 0
        retry_count = 0
        
        while retry_count < max_retries and not compare_list:
            retry_count += 1
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            ocrresults = context.run_recognition(
                "UtilsOCR",
                current_image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": roi,
                                "expected": [""],
                            }
                        }
                    }
                }
            )

            print(f"OCR best_results: {ocrresults.best_result}, total filtered results: {len(ocrresults.filtered_results)}")
            # 如果成功获取结果，则跳出循环
            if ocrresults.best_result:
                has_valid_text = any(res.text and res.text.strip() for res in ocrresults.filtered_results)
                if has_valid_text:
                    break
            
            if retry_count < max_retries:
                print(f"[DEBUG] OCR result not ready, retrying... ({retry_count}/{max_retries})")
            time.sleep(2)
        
        if retry_count >= max_retries:
            print(f"[WARNING] Max retries reached for OCR, proceeding with empty results")
        
        # 统计各语言数量
        for res in (ocrresults.filtered_results if not compare_list else compare_list):
            ignore_match = False
            if isinstance(res, str):
                text = res
            else:
                text = res.text
            if ignore and not compare_list:
                for ign in ignore:
                    if match_mgr.fuzzy_match(ign, text):
                        print(f"[DEBUG] Ignoring result due to ignore keyword: {ign}")
                        ignore_match = True
                        break
            
            if ignore_match:
                continue

            # 检查日文假名（平假名和片假名）
            if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
                jp += 1
                continue
            
            # 使用 hanzidentifier 判断中文
            lang_id = hanzidentifier.identify(text)
            if lang_id == hanzidentifier.SIMPLIFIED:
                cn += 1
            elif lang_id == hanzidentifier.TRADITIONAL:
                tw += 1
            elif lang_id == hanzidentifier.MIXED or lang_id == hanzidentifier.BOTH:
                cn += 1
            
            # 检查英文
            if re.search(r'[a-zA-Z]', text):
                en += 1
        
        return {"jp": jp, "cn": cn, "tw": tw, "en": en}

    @staticmethod
    def detect_lang(context, roi, ignore: list = None, compare_list: list = None):
        """
        returns:
            str: "jp"（日文）、"cn"（简体中文）、"tw"（繁体中文）或 "en"（英文），表示检测到的主要语言类型
        """
        jp = cn = tw = en = 0
        max_retries = 30
        
        # 获取需要处理的 ROI 列表
        roi_list = roi if ActUtils.get_list_depth(roi) != 1 else [roi]

        print(f"[DEBUG] Ignore list for language detection: {ignore}")
        
        # 对每个 ROI 进行 OCR 识别和语言统计
        for current_roi in roi_list:
            lang_counts = ActUtils._run_ocr_and_count_lang(context, current_roi, max_retries, ignore, compare_list)
            jp += lang_counts["jp"]
            cn += lang_counts["cn"]
            tw += lang_counts["tw"]
            en += lang_counts["en"]
        
        # 返回计数最多的语言类型
        lang_counts = {"jp": jp, "cn": cn, "tw": tw, "en": en}
        result = max(lang_counts, key=lang_counts.get)
        print(f"[DEBUG] Language detection: {lang_counts}, selected: {result}")
        info_share.current_lang = result
        return result 

    @classmethod
    def choose_filter(cls, context, element: str = None, rarity: int = None, weapon: str = None, AR_mode: bool = False):
        if AR_mode:
            lang_roi = [603,14,676,65]
        else:
            lang_roi = [126,22,508,91]

        lang_mode = act_mgr.detect_lang(context, lang_roi)
        print(f"[DEBUG] Detected language mode: {lang_mode}")
        if lang_mode == "jp":
            markers = ["フィルタ", "全フィルタ解除", "OK", "装備可能のみ"]
        if lang_mode == "cn":
            markers = ["筛选", "解除所有筛选", "确定", "只能装备"]
        if lang_mode == "tw":
            markers = ["篩選", "解除所有篩選", "OK", "只能裝備"]
        if lang_mode == "en":
            markers = ["Filter", "Reset Filter", "OK", "Can be Equipped only"]

        for marker, roi in zip([markers[0], markers[1]], [[640,0,340,135], [22,537,375,181]]):
            print(f"[DEBUG] Attempting to click marker: {marker} in ROI: {roi}")       
            open_finish = context.run_task(
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
                        },
                        "timeout": 20000
                    }
                }
            )
        if not open_finish:
            print(f"[ERROR] Failed to click filter for {element} {rarity}* {weapon}")
            return False
        
        # 当 AR_mode=True 时，element 和 weapon 可能为 None
        element_path = Path(cls.UI_DATA.get("element", {}).get(element, "")) if element else None
        rarity_path = Path(cls.UI_DATA.get("rarity", {}).get(str(rarity), "")) if rarity else None
        weapon_path = Path(cls.UI_DATA.get("weapon", {}).get(weapon, "")) if weapon else None
        
        if AR_mode:
            path_list = ["ar_mode", rarity_path]
            roi_list = [[53,208,563,144], [667,215,553,114]]
        else: 
            path_list = [element_path, weapon_path, rarity_path]
            roi_list = [[59,216,353,262], [467,215,347,340], [869,216,349,229]]
        
        # 初始化标志变量
        ifsuit_finish = True
        
        for path, roi in zip(path_list, roi_list):
            # 跳过 None 的路径
            if path is None:
                continue
            
            if isinstance(path, Path):
                path = str(path)
            path = cls.normalize_template_path(path)
            if path == "ar_mode":
                ifsuit_finish = context.run_task(
                    "UtilsOCR",
                    pipeline_override={
                        "UtilsOCR": {
                            "recognition": {
                                "param": {
                                    "roi": roi,
                                    "expected": markers[3]
                                }
                            },
                            "action":{
                                "type": "Click"
                            }
                        }
                    }
                )
                if not ifsuit_finish:
                    return False
                continue
                
            print(f"[DEBUG] Attempting to click filter with template: {path}")
            context.run_task(
                "UtilsTemplateMatch",
                pipeline_override={
                    "UtilsTemplateMatch" :{
                        "recognition":{
                            "param":{
                                "roi": roi,
                                "template": str(path),
                                "order_by": "score"
                            }
                        },
                        "action":{
                            "type": "Click"
                        }
                    }
                }
            )

        filter_finish = context.run_task(
                "UtilsOCR",
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "expected": markers[2]
                            }
                        },
                        "action":{
                            "type": "Click"
                        }
                    }
                }
            )
        
        if not filter_finish:
            print(f"[ERROR] Failed to confirm filter for {element} {rarity}* {weapon}")
            return False
        return True


act_mgr = ActUtils
