from collections import Counter
import random


class ActUtils:
    DEFAULT_BEGIN = [330, 530, 5, 5]
    DEFAULT_END = [330, 15, 5, 5]

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
    def choose_best(res: dict, keywords: list, mode: str = "best"):
        """
        args:
            res: 识别结果字典，包含多个 res_* 键，每个键对应一个识别结果
            keywords: 关键词列表，用于匹配识别结果中的文本, 优先级从左到右
            mode: 选择模式:
                "first": 选择keywords中第一个关键词的最大值
                "best": 选择keywords中拥有所有关键词best最多的结果
        """
        output = {}
        key_mapping = {}  # 存储 res_data -> res_key 的对应关系
        
        if isinstance(keywords, str):
            keywords = [keywords]
        
        for keyword in keywords:
            best = -1
            best_data = None
            best_key = None
            for char_name_dict in res.values():
                for char_id_dict in char_name_dict.values():
                    for res_key, res_data in char_id_dict.items():
                        if not res_data.get(keyword):
                            continue

                        value = int(res_data.get(keyword))
                        if value > best:
                            best = value
                            best_data = res_data
                            best_key = res_key
                
            if best_data:
                output[keyword] = best_data
                # 将 res_data（字典）转为可哈希的字符串来建立映射
                key_mapping[id(best_data)] = best_key
        
        if mode == "first":
            most_common_data = output.get(keywords[0], None)
        elif mode == "best":
            # 按对象身份统计哪个 res_data 出现最多（dict 不可哈希，不能直接用 Counter）
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
                            return res_key
        
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


act_mgr = ActUtils
