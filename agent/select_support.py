from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import random
import json
import actutils


# 在这里比较数据

@AgentServer.custom_action("SelectSupport")
class SelectSupport(CustomAction):
    def __init__(self):
        super().__init__()
        self.all_res = {}
        self.last_fingerprint = []

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        # 检查超时
        if actutils.timeout_mgr.check_timeout(argv.node_name):
            return False
        
        # 重置实例状态，防止跨调用残留
        self.all_res = {}
        self.last_fingerprint = []

        # 初始化
        page = 0
        idroi = [45,190,400,530]
        param = json.loads(argv.custom_action_param) if isinstance(argv.custom_action_param, str) else argv.custom_action_param
        
        current_fingerprint = [0]

        while actutils.act_mgr.if_bottom(self.last_fingerprint, current_fingerprint):
            # 截取新画面
            context.tasker.controller.post_screencap().wait()
            current_image = context.tasker.controller.cached_image()
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
                                    "custom_recognition_param": param
                                }
                            }
                        }
                    }
                )
            
            current_fingerprint, fpbox = actutils.match_mgr.group_info(context, current_image, idroi, "RANK", -25, -105)
                 
            # 解析识别结果
            if not recres:
                print("[DEBUG] Recognition failed completely")
                add_res = {}
            else:
                rbox = [recres.box[0], recres.box[1], recres.box[2], recres.box[3]]
                if rbox == [-1, -1, -1, -1]:
                    print(f"[DEBUG] Failed to find character: {param['name']} {param['id']}")
                    add_res = {}
                else:
                    # 从 best_result.detail 获取结果（三层嵌套 {name: {id: {res_*: entry}}}）
                    detail = recres.best_result.detail if recres.best_result else {}
                    add_res = json.loads(detail) if isinstance(detail, str) else (detail or {})
                    if rbox == [0, 0, 0, 0]:
                        print(f"[DEBUG] Found multiple characters")
                    else:
                        print(f"[DEBUG] Found one character: {param['name']} {param['id']}")
                    
            # 为每个 res_* 添加 pos 信息
            if add_res and actutils.act_mgr.if_bottom(self.last_fingerprint, current_fingerprint):
                print(f"[DEBUG] Updated recognition results: {add_res}")
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
                            res_box = res_data.get("box", [0, 0, 0, 0])
                            for i, fp in enumerate(fpbox):
                                if actutils.act_mgr.in_roi(fp, res_box):
                                    res_data["pos"] = i + page
                                    break
                self.all_res = actutils.match_mgr.merge_res_dicts(self.all_res, add_res)
                
            actutils.act_mgr.swipe(context, [330, 530, 5, 5], [330, 15, 5, 5])
            self.last_fingerprint = current_fingerprint
            page += 3

        # 选择最佳结果
        best_res = actutils.act_mgr.choose_best(self.all_res, ["Level", "ATK", "HP"], mode="best")
        print(f"[DEBUG] Best result: {best_res}")

        if not best_res:
            print("[DEBUG] No suitable result found")
            actutils.timeout_mgr.stop_monitoring(argv.node_name)
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
                        swipe_time = (res_data.get("pos", 0) + 1) // 3
                        raw_box = res_data.get("box")
                        found = True
                        break

        if not raw_box:
            print("[DEBUG] Could not find box for best result")
            actutils.timeout_mgr.stop_monitoring(argv.node_name)
            return False

        # 滑动到顶部
        temp = 0
        while temp < (page / 3):
            actutils.act_mgr.swipe(context, [330, 15, 5, 5], [330, 530, 5, 5])
            temp += 1
        
        # 滑动到对应位置
        temp = 0
        while temp < swipe_time:
            actutils.act_mgr.swipe(context, [330, 530, 5, 5], [330, 15, 5, 5])
            temp += 1

        # 点击（范围为icon左移一个单位边长）
        x1 = max(0, raw_box[0] + random.randint(0, int(raw_box[2])) - raw_box[2] - 5)
        y1 = max(0, raw_box[1] + random.randint(0, int(raw_box[3])))
        context.tasker.controller.post_click(x1, y1).wait()

        actutils.timeout_mgr.stop_monitoring(argv.node_name)
        return True