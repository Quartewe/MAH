from difflib import SequenceMatcher
import copy


class MatchUtils:
    @staticmethod
    def merge_res_dicts(existing: dict, new: dict) -> dict:
        """
        合并三层嵌套字典：{name: {id: {res_*: entry}}}
        将 new 中的 res_* 键重新编号后追加到 existing 中对应的 name/id 下
        """
        if not existing:
            return copy.deepcopy(new)
        if not new:
            return existing
        
        merged = copy.deepcopy(existing)
        
        for name, id_dict in new.items():
            if not isinstance(id_dict, dict):
                continue
            if name not in merged:
                merged[name] = {}
            for char_id, res_dict in id_dict.items():
                if not isinstance(res_dict, dict):
                    continue
                if char_id not in merged[name]:
                    merged[name][char_id] = {}
                
                # 找出 merged[name][char_id] 中已有的最大 res 索引
                max_idx = -1
                for key in merged[name][char_id].keys():
                    if isinstance(key, str) and key.startswith("res_"):
                        try:
                            idx = int(key.split("_")[1])
                            max_idx = max(max_idx, idx)
                        except (ValueError, IndexError):
                            pass
                
                new_start_idx = max_idx + 1
                
                # 将 new 中的 res_* 重新编号后加入
                for key, val in res_dict.items():
                    if isinstance(key, str) and key.startswith("res_"):
                        try:
                            old_idx = int(key.split("_")[1])
                            new_key = f"res_{new_start_idx + old_idx}"
                            merged[name][char_id][new_key] = val
                        except (ValueError, IndexError):
                            pass
        
        return merged

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
    
    @staticmethod
    def group_info(context, image, roi: list, filter_id: str, x_range: int, y_range: int):
        """
        分组信息：根据基准点和目标点的相对位置关系，将文本分为不同组别

        Args:
            context: MaaFramework 上下文
            image: 当前图像
            roi: 识别区域
            filter_id: 过滤ID
            x_range 水平范围, 以基准点为中心的左负右正
            y_range 垂直范围, 以基准点为中心的上负下正

        Returns:
            output: list 给fingerprint用的
            box: list 给fingerprint用的
        """

        res = context.run_recognition(
            "UtilsOCR",
            image,
            pipeline_override={
                "UtilsOCR": {
                    "recognition": {
                        "param": {
                            "roi": roi,
                            "expect": filter_id
                        }
                    }
                }
            }
        )
        output = []
        box = []
        if not res or not res.hit:
            return output, box
        
        # 使用集合记录已添加的文本位置，避免重复（基于box坐标去重）
        added_boxes = set()
        # 黑名单：过滤不想要的文本
        blacklist = ["最后登录", "RANK"]
        
        for fr in res.filtered_results:
            for text in res.all_results:
                # 跳过黑名单文本
                if text.text.strip() in blacklist:
                    continue
                    
                diff_x = text.box[0] - fr.box[0]
                diff_y = text.box[1] - fr.box[1]
                
                # 将box转为可哈希的元组用于去重
                box_tuple = tuple(text.box)
                
                if (min(0, x_range) <= diff_x <= max(0, x_range) and 
                    min(0, y_range) <= diff_y <= max(0, y_range) and 
                    not match_mgr.fuzzy_match(text.text.strip(), fr.text.strip()) and
                    box_tuple not in added_boxes):  # 检查是否已添加
                    output.append(text.text.strip())
                    box.append(text.box)
                    added_boxes.add(box_tuple)  # 记录已添加的box
                    
        return output, box


match_mgr = MatchUtils
