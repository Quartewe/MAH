from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
import json
from pathlib import Path
from actutils import data_io
from actutils import match_mgr


@AgentServer.custom_recognition("TraverseMatch")
class TraverseMatch(CustomRecognition):
    def __init__(self):
        super().__init__()
        self.BASE_PATH = Path("assets/resource/image")
        self.CHAR_DATA = data_io.read_data("data/characters.json")
        self.AR_DATA = data_io.read_data("data/ar.json")
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        
        # 处理 custom_recognition_param，MAA 框架会自动转换为 JSON 字符串或字典
        param_raw = argv.custom_recognition_param
        param = {}
        print(f"[DEBUG] param_raw type: {type(param_raw)}, value: {param_raw}")
        
        # 如果是字符串，进行 JSON 解析
        if isinstance(param_raw, str):
            if param_raw:
                try:
                    param = json.loads(param_raw)
                    print(f"[DEBUG] JSON 解析成功, param type: {type(param)}")
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"[DEBUG] JSON 解析失败: {e}")
                    param = {}
        elif isinstance(param_raw, dict):
            # 直接传字典时，MAA 会将其转换为字符串，所以这个分支可能不会执行
            param = param_raw
            print(f"[DEBUG] param_raw 本身是字典")
        else:
            print(f"[DEBUG] param_raw 类型: {type(param_raw)}")
        
        char_name = param.get("name", None)
        char_id = param.get("id", None)
        if isinstance(param.get("id"), int):
            char_id = f"{param.get('id'):02d}"
        
        print(f"[DEBUG] char_name: {char_name}, char_id: {char_id}")

        # 判断是否为 AR 模式：当没有角色名或角色ID时，尝试 AR 模式
        if not char_name or not char_id:
            ar_mode = True
            # 只有当 param 中有 AR 数据时才能进行 AR 识别
            ar_data = param.get("AR", None).get("name", None)
            if ar_data and isinstance(ar_data, dict):
                ar_name = ar_data.get("name", None)
                if ar_name and ar_name in self.AR_DATA:
                    template_path = Path(self.AR_DATA[ar_name]["path"].strip().strip('"').strip("'"))
                else:
                    print(f"[DEBUG] Invalid AR name: {ar_name}")
                    return CustomRecognition.AnalyzeResult(box=None, detail=None)
            else:
                print("[DEBUG] No valid AR data provided")
                return CustomRecognition.AnalyzeResult(box=None, detail=None)
        else:
            ar_mode = False
            template_path = Path(self.CHAR_DATA[char_name][char_id]["path"].strip().strip('"').strip("'"))
        
        match_detail = None
        template = None

        if template_path and template_path.exists() and not ar_mode:
            for template in template_path.rglob("*.png"):
                template = template.relative_to(self.BASE_PATH)
                print(f"[DEBUG] Finging Character: {template}")
                match_detail = context.run_recognition(
                    "UtilsFeatureMatch",
                    argv.image,
                    pipeline_override={
                        "UtilsFeatureMatch": {
                            "recognition": {
                                "param": {"template": str(template)}
                            }
                        }
                    }
                )
  
                if match_detail.box:
                    print(f"[DEBUG] Found Character: {template}，Location: {match_detail.box}")
                    break
                else:
                    print("[DEBUG] 未找到匹配项")
        elif template_path and template_path.exists() and ar_mode:
            template = template_path.relative_to(self.BASE_PATH)
            print(f"[DEBUG] Finding AR: {template}")
            match_detail = context.run_recognition_direct(
                "FeatureMatch",
                {"template": str(template)},
                argv.image
                )
  
            if match_detail.box:
                print(f"[DEBUG] Found AR: {template}，Location: {match_detail.box}")
        
        else:
            print(f"[DEBUG] Template path does not exist: {template_path}")
        
        return CustomRecognition.AnalyzeResult(
            box=match_detail.box if match_detail and match_detail.box else None, 
            detail={"path": str(template),
                    "name": char_name,
                    "id": char_id,
                    "iffriend": False
                    } if match_detail and match_detail.box and not ar_mode else 
                    {"path": str(template),
                    "name": ar_name,
                     } if match_detail and match_detail.box else None
        )
    
@AgentServer.custom_recognition("GroupAvatarInfo")
class GroupAvatarInfo(CustomRecognition):
    def __init__(self):
        super().__init__()
        self.ROI = [456, 21 , 965, 155] #块
        # self.roi = [15,170,1255,550] #识别范围
        self.DEAFAULT_PARAM_A = {
            "name": "kyouma",
            "id": 2,
            "Level": 70,
            "S.A.Lv": 1,
            "Skill": 100,
            "ATK": 0,
            "HP": 0,
            "AR": {
                "name": None,
                "matched": False
                },
            "iffriend": True
        }
        self.DEAFAULT_PARAM_B = {
            "name": "kyouma",
            "id": 2,
            "SLevel": 0,
            "S.A.Lv": 1,
            "SSkill": 0,
            "SATK": 0,
            "SHP": 0,
            "AR": {
                "name": None,
                "matched": False
                },
            "iffriend": True
        }
    
    
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        param = argv.custom_recognition_param
        
        # 处理参数：可能是字符串（JSON）或字典
        if isinstance(param, str):
            try:
                param = json.loads(param)
                template_type = param.get("template_type", "A")
                print("[DEBUG] 已解析")
            except json.JSONDecodeError as e:
                print(f"[DEBUG] 无法解析参数: {e}，将使用默认参数")
                param = self.DEAFAULT_PARAM_A
                template_type = "A"
        elif isinstance(param, dict):
            template_type = param.get("template_type", "A")
        else:
            print(f"[DEBUG] 参数类型错误: {type(param)}, 将使用默认参数")
            param = self.DEAFAULT_PARAM_A
            template_type = "A"

        output = {
            param["name"]: {
                param["id"]: {
                    "Level": param.get("Level", self.DEAFAULT_PARAM_A["Level"] if template_type == "A" else None),
                    "SLevel": param.get("SLevel", self.DEAFAULT_PARAM_B["SLevel"] if template_type == "B" else None),
                    "Skill": param.get("Skill", self.DEAFAULT_PARAM_A["Skill"]  if template_type == "A" else None),
                    "SSkill": param.get("SSkill", self.DEAFAULT_PARAM_B["SSkill"] if template_type == "B" else None),
                    "S.A.Lv": param.get("S.A.Lv", self.DEAFAULT_PARAM_B["S.A.Lv"] if template_type == "B" else self.DEAFAULT_PARAM_A["S.A.Lv"]),
                    "ATK": param.get("ATK", self.DEAFAULT_PARAM_A["ATK"] if template_type == "A" else None),
                    "SATK": param.get("SATK", self.DEAFAULT_PARAM_B["SATK"] if template_type == "B" else None),
                    "HP": param.get("HP", self.DEAFAULT_PARAM_A["HP"] if template_type == "A" else None),
                    "SHP": param.get("SHP", self.DEAFAULT_PARAM_B["SHP"] if template_type == "B" else None),
                    "AR": {
                        "name": param.get("AR", None),
                        "matched": True
                    },
                    "iffriend": True,
                    "path": None
                }
            }
        }

        # character
        avatar = context.run_recognition(
            "TraverseMatch",
            argv.image,
            pipeline_override={
                "TraverseMatch": {
                    "recognition": {
                        "type": "Custom",
                        "param": {
                            "custom_recognition": "TraverseMatch",
                            "custom_recognition_param": {
                                "name": param["name"],
                                "id": param["id"]
                            }
                        }
                    }
                }
            }
        )
        print(f"[DEBUG] avatar: {avatar}")
        
        if not avatar or not avatar.box:
            print(f"[DEBUG] Failed to find character: {param['name']} {param['id']}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        
        # 获取详细信息，best_result.detail 包含识别结果
        detail_dict = {}
        if avatar.best_result and avatar.best_result.detail:
            try:
                detail_dict = json.loads(avatar.best_result.detail)
            except (json.JSONDecodeError, TypeError):
                detail_dict = {}
        
        output[param["name"]][param["id"]]["path"] = detail_dict.get("path") if detail_dict else None
        
        if detail_dict:
            print(f"[DEBUG] found character: {detail_dict.get('name')} {detail_dict.get('id')} at {avatar.box}, path: {detail_dict.get('path')}")
        if avatar.box:
            ROI = [avatar.box[0]-self.ROI[0], avatar.box[1]-self.ROI[1], self.ROI[2], self.ROI[3]] # 块
            print(f"[DEBUG] ROI for character {param['name']} {param['id']}: {ROI}")
        else:
            return CustomRecognition.AnalyzeResult(box=None, detail=param)
        
        # Level and Skill and ATK HP
        if template_type == "A":
            res = context.run_recognition(
                "UtilsOCR",
                argv.image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": ROI,
                                "expect": "\\d+"
                            }
                        }
                    }
                }
            )

            texts  = res.all_results
            nums = res.filtered_results

            for text in texts:
                if match_mgr.fuzzy_match(text.text, "Level", 0.8):
                    for num in nums:
                        if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                            levres = [int(temp) for temp in num.text.split("/")]
                            output[param["name"]][param["id"]]["Level"] = levres[0]
                            print(f"Found Level: {levres[0]} for character {param['name']} {param['id']}")
                            break
                    continue
                elif match_mgr.fuzzy_match(text.text, ["Skill/S.A.Lv", "SkilI/S.A.Lv"], 0.8):
                    for num in nums:
                        if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                            skillres = [int(temp) for temp in num.text.split("/")]
                            output[param["name"]][param["id"]]["Skill"] = skillres[0]
                            output[param["name"]][param["id"]]["S.A.Lv"] = skillres[1]
                            print(f"Found Skill: {skillres[0]} and S.A.Lv: {skillres[1]} for character {param['name']} {param['id']}")
                            break
                    continue
                elif match_mgr.fuzzy_match(text.text, "HP", 0.8):
                    for num in nums:
                        if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                            hpres = int(num.text)
                            output[param["name"]][param["id"]]["HP"] = hpres
                            print(f"Found HP: {hpres} for character {param['name']} {param['id']}")
                            break
                    continue
                elif match_mgr.fuzzy_match(text.text, "ATK", 0.8):
                    for num in nums:
                        if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                            atkres = int(num.text)
                            output[param["name"]][param["id"]]["ATK"] = atkres
                            print(f"Found ATK: {atkres} for character {param['name']} {param['id']}")
                            break
                    continue


        if template_type == "B":
            res = context.run_recognition(
                "UtilsOCR",
                argv.image,
                pipeline_override={
                    "UtilsOCR": {
                        "recognition": {
                            "param": {
                                "roi": [ROI[0]+895, ROI[1]+15, ROI[2]-895, ROI[3]-15],
                                "expect": "\\d+"
                            }
                        }
                    }
                }
            )
            texts = res.filtered_results
            texts = sorted(texts, key=lambda x: x.box[1])
            output[param["name"]][param["id"]]["SLevel"] = int(texts[0].text)
            print(f"[DEBUG] Found Seed Level: {texts[0].text} for character {param['name']} {param['id']}")
            output[param["name"]][param["id"]]["SSkill"] = int(texts[1].text)
            print(f"[DEBUG] Found Seed Skill: {texts[1].text} for character {param['name']} {param['id']}")
            output[param["name"]][param["id"]]["SHP"] = int(texts[2].text)
            print(f"[DEBUG] Found Seed HP: {texts[2].text} for character {param['name']} {param['id']}")
            output[param["name"]][param["id"]]["SATK"] = int(texts[3].text)
            print(f"[DEBUG] Found Seed ATK: {texts[3].text} for character {param['name']} {param['id']}")

        if param.get("AR").get("name") is not None:
            ar_name = param.get("AR")
            ar_result = context.run_recognition(
                "TraverseMatch",
                argv.image,
                pipeline_override={
                    "TraverseMatch": {
                        "recognition": {
                            "type": "Custom",
                            "param": {
                                "custom_recognition": "TraverseMatch",
                                "custom_recognition_param": {
                                    "AR": {
                                        "name": ar_name
                                    }
                                }
                            }
                        }
                    }
                }
            )
            
            # AR 结果：嵌套字典包含 name 和 matched 状态
            output[param["name"]][param["id"]]["AR"] = {
                "name": ar_name,
                "matched": bool(ar_result and ar_result.box)
            }
            print(f"[DEBUG] AR recognition for {ar_name}: {'matched' if ar_result and ar_result.box else 'not matched'}")
        else: print("[DEBUG] No AR specified, skipping AR recognition.")
        
        return CustomRecognition.AnalyzeResult(
            box=ROI if avatar and avatar.box else None,
            detail=output if avatar and avatar.box else None
        )