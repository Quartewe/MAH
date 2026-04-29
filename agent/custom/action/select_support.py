from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import random
import json
from os.path import commonprefix
from utils import timeout_mgr, match_mgr, act_mgr, data_io, proj_path, info_share


@AgentServer.custom_action("SelectSupport")
class SelectSupport(CustomAction):
    def __init__(self):
        super().__init__()
        self.all_res = {}
        self.last_fingerprint = []
        self.DATA_PATH = proj_path.AUTO_COMBAT_DIR
        self.UI_DATA = data_io.read_data(proj_path.UI_FILE)
        self.CHAR_DATA = data_io.read_data(proj_path.CHAR_FILE)
        self.raw_box = None
        self.swipe_time = 0
        self.page = 0

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if timeout_mgr.check_timeout(argv.node_name):
            return False
        
        # 重置实例状态，防止跨调用残留
        self.all_res = {}
        self.last_fingerprint = []

        # 初始化
        idroi = [45,190,400,530]
        param = json.loads(argv.custom_action_param)
        default_mode = False
        if isinstance(param, dict):
            # 单字典模式
            support_data = param
        if isinstance(param, str):
            param = param.strip('"')
            print(f"[DEBUG] 目标文件: {param}")
            if not param:
                print(f"[DEBUG] 未指定要搜索的目标文件")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
            try:
                raw_data = data_io.find_target_files(self.DATA_PATH, param)
                if raw_data:
                    team_data = raw_data.get("team", {})
                    support_data = team_data.get("SUPPORT", {})
                    print(f"[DEBUG] 助战数据: {support_data}")
                else:
                    support_data = None
            except Exception as e:
                print(f"[ERROR] 查找目标文件失败: {e}")
                timeout_mgr.stop_monitoring(argv.node_name)
                return False
            
        if not support_data:
            print(f"[WARNING] 目标文件中未找到助战数据，使用默认数据")
            default_mode = True
            support_data = {
                "name": "kyouma",
                "id": 2
            }

        if support_data and not default_mode:    
            keywords = list(support_data.keys())
            for key_to_remove in ["name", "id", "AR", "label"]:
                if key_to_remove in keywords:
                    keywords.remove(key_to_remove)
        select_mode = support_data.get("select_mode", "best")

        support_data["name"] = support_data.get("name", "").lower()
        support_data["id"] = int(support_data.get("id", 0))
        
        context.run_task(
                    "UtilsTemplateMatch",
                    pipeline_override={
                        "UtilsTemplateMatch": {
                            "recognition":{
                                "param": {
                                    "template": "fight/support/support_default.png",
                                    "threshold": 0.8,
                                    "roi": [110,93,799,72]
                                }
                            },
                            "action":{
                                "type": "Click"
                            }
                        }
                    }
                )

        # 扫描并选择最佳支援
        if not self._scan_and_select_support(context, support_data if not default_mode else None, keywords, select_mode, idroi):
            # 滑动到顶部
            page = self.page
            temp = 0
            while temp < (page // 3):
                print(f"[DEBUG] 正在滑动到顶部，进度 {temp}/{(page // 3)}")
                context.run_action(
                    "UtilsSwipe",
                    pipeline_override={
                        "UtilsSwipe": {
                            "begin":[400, 180, 5, 5],
                            "end":[400, 680, 5, 5]
                        }
                    }
                )
                temp += 1
            id_format = f"{support_data.get('id', ''):02d}"
            support_name = support_data.get("name", "")
            print(f"[DEBUG] 助战名称: {support_name}, 编号: {id_format}")
            support_details = self.CHAR_DATA.get(support_name, {}).get(id_format, {})
            print(f"[DEBUG] 助战详情: {support_details}")
            element = support_details.get("element", "")
            print(f"[DEBUG] 属性: {element}")
            element_filter = self.UI_DATA.get("support", {}).get(element if element != "god" else "default", "")
            template_element_filter = commonprefix([element_filter, str(proj_path.IMAGE_DIR)])
            print(f"[DEBUG] 未找到精确匹配，尝试按属性筛选: {element_filter}")
            if element_filter:
                context.run_task(
                    "UtilsTemplateMatch",
                    pipeline_override={
                        "UtilsTemplateMatch": {
                            "recognition":{
                                "param": {
                                    "template": element_filter,
                                    "threshold": 0.8,
                                    "roi": [110,93,799,72]
                                }
                            },
                            "action":{
                                "type": "Click"
                            }
                        }
                    }
                )
                if not self._scan_and_select_support(context, support_data if not default_mode else None, keywords, select_mode, idroi):
                    print("[DEBUG] 属性筛选失败，未选择到助战")
                    timeout_mgr.stop_monitoring(argv.node_name)
                    return False

        raw_box = self.raw_box
        swipe_time = self.swipe_time
        page = self.page

        # 滑动到顶部
        temp = 0
        while temp < (page // 3):
            print(f"[DEBUG] 正在滑动到顶部，进度 {temp}/{(page // 3)}")
            context.run_action(
                "UtilsSwipe",
                pipeline_override={
                    "UtilsSwipe": {
                        "begin":[400, 180, 5, 5],
                        "end":[400, 680, 5, 5]
                    }
                }
            )
            temp += 1

        # 滑动到对应位置
        temp = 0
        print(f"[DEBUG] 需要滑动 {swipe_time} 次以到达目标位置")
        while temp < swipe_time:
            print(f"[DEBUG] 正在滑动到目标位置，进度 {temp}/{swipe_time}")
            context.run_action(
                "UtilsSwipe",
                pipeline_override={
                    "UtilsSwipe": {
                        "begin":[330, 630, 5, 5],
                        "end":[330, 115, 5, 5]
                    }
                }
            )
            temp += 1
        
        if raw_box is None:
            print("[DEBUG] 没有可点击区域，终止")
            timeout_mgr.stop_monitoring(argv.node_name)
            return False

        # 点击（范围为icon左移一个单位边长）
        x1 = max(0, raw_box[0] + random.randint(0, int(raw_box[2])) - raw_box[2] - 5)
        y1 = max(0, raw_box[1] + random.randint(0, int(raw_box[3])))
        context.tasker.controller.post_click(x1, y1).wait()

        timeout_mgr.stop_monitoring(argv.node_name)
        return True

    def _scan_and_select_support(self, context, support_data, keywords, select_mode, idroi):
        """扫描支援角色并选择最佳结果
        
        返回值：bool，是否成功找到最佳结果
        成功时设置：self.raw_box, self.swipe_time, self.page
        """
        current_fingerprint = [0]
        self.raw_box = []
        self.swipe_time = 0
        self.page = 0
        page = 0
        while True:
            # 截取新画面
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image
            add_res = {}
            
            recres = context.run_recognition(
                    "GroupAvatarInfo",
                    current_image,
                    pipeline_override={
                        "GroupAvatarInfo": {
                            "recognition": {
                                "type": "Custom",
                                "param": {
                                    "custom_recognition": "GroupAvatarInfo",
                                    "custom_recognition_param": support_data
                                }
                            }
                        }
                    }
                )

            current_fingerprint, fpbox = match_mgr.group_info(context, current_image, idroi, "RANK", -25, -105)
            
            # 检查是否已到底部（指纹重复）
            if not act_mgr.if_bottom(self.last_fingerprint, current_fingerprint):
                print("[DEBUG] 已到列表底部，停止滚动")
                break
                 
            # 解析识别结果
            if not recres:
                print("[DEBUG] 识别完全失败")
                add_res = {}
            else:
                rbox = [recres.box[0], recres.box[1], recres.box[2], recres.box[3]] if recres.box else None
                if rbox is None:
                    print(f"[DEBUG] 未找到角色: {support_data['name']} {support_data['id']}")
                    add_res = {}
                else:
                    # 从 best_result.detail 获取结果（三层嵌套 {name: {id: {res_*: entry}}}）
                    detail = recres.best_result.detail if recres.best_result else {}
                    add_res = json.loads(detail) if isinstance(detail, str) else (detail or {})
                    if rbox == [0, 0, 1, 1]:
                        print(f"[DEBUG] 找到多个角色")
                    else:
                        print(f"[DEBUG] 找到一个角色: {support_data['name']} {support_data['id']}")
                    
            # 为每个 res_* 添加 pos 信息
            if add_res:
                print(f"[DEBUG] 已更新识别结果: {add_res}")
                for name, id_dict in add_res.items():
                    if not isinstance(id_dict, dict):
                        continue
                    for char_id, res_dict in id_dict.items():
                        if not isinstance(res_dict, dict):
                            continue
                        for res_key, res_data in res_dict.items():
                            if not res_key.startswith("res_"):
                                continue
                            # 根据 fpbox 确定该角色在当前页的位置
                            res_box = res_data.get("box", [0, 0, 1, 1])
                            print(f"[DEBUG] 正在处理结果 {res_key}，box={res_box}")
                            for i, fp in enumerate(fpbox):
                                print(f"[DEBUG] 检查指纹框 {fp} 与结果框 {res_box} 的关系")
                                if act_mgr.in_roi(res_box, fp):
                                    res_data["pos"] = i + page
                                    print(f"[DEBUG] 结果框 {res_box} 位于指纹框 {fp} 内")
                                    break
                                else:
                                    print(f"[DEBUG] 结果框 {res_box} 不在指纹框 {fp} 内")
                self.all_res = match_mgr.merge_res_dicts(self.all_res, add_res)
            
            print(f"[DEBUG] 第 {page // 3} 页，指纹: {current_fingerprint}，正在滑动...")
            context.run_action(
                "UtilsSwipe",
                pipeline_override={
                    "UtilsSwipe": {
                        "begin":[330, 530, 5, 5],
                        "end":[330, 15, 5, 5]
                    }
                }
            )
            self.last_fingerprint = current_fingerprint
            page += 3

        # 选择最佳结果
        best_res = act_mgr.choose_best(self.all_res, support_data, keywords, mode=select_mode)
        print(f"[DEBUG] 最佳结果: {best_res}")
        print(f"[DEBUG] 页数: {page}")

        if not best_res:
            print("[DEBUG] 未找到合适结果")
            self.page = page
            return False

        # 从 all_res 中找到最佳结果的数据
        raw_box = None
        swipe_time = 0
        found = False
        for char_name_dict in self.all_res.values():
            if found:
                break
            for char_id_dict in char_name_dict.values():
                if found:
                    break
                for res_key, res_data in char_id_dict.items():
                    if res_key == best_res:
                        swipe_time = res_data.get("pos", 0) // 3
                        print(f"[DEBUG] 需要滑动次数: {swipe_time}")
                        raw_box = res_data.get("box")
                        found = True
                        break

        if not raw_box:
            print("[DEBUG] 未找到最佳结果对应的点击框")
            return False

        # 保存结果到实例变量
        self.raw_box = raw_box
        self.swipe_time = swipe_time
        self.page = page
        return True
