from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
import json
import re
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

        def extract_skin_from_template(template_str: str) -> str:
            stem = Path(template_str).stem
            match = re.search(r"(skin\d+|default)$", stem, re.IGNORECASE)
            if match:
                return match.group(1).lower()
            for part in reversed(stem.split("_")):
                if re.fullmatch(r"skin\d+|default", part, re.IGNORECASE):
                    return part.lower()
            return stem

        if template_path and template_path.exists() and not ar_mode:
            # 辅助函数：判断两个 box 位置是否近似（中心点距离在阈值内视为同一对象）
            def _boxes_similar(box_a, box_b, threshold=10):
                cx_a, cy_a = box_a[0] + box_a[2] / 2, box_a[1] + box_a[3] / 2
                cx_b, cy_b = box_b[0] + box_b[2] / 2, box_b[1] + box_b[3] / 2
                return abs(cx_a - cx_b) < threshold and abs(cy_a - cy_b) < threshold

            # 第一步：遍历全部模板，收集所有 filtered_results 中的 (box, count, template) 
            all_hits = []
            for tpl_file in template_path.rglob("*.png"):
                tpl_rel = tpl_file.relative_to(self.BASE_PATH)
                print(f"[DEBUG] Finding Character: {tpl_rel}")
                reco_result = context.run_recognition(
                    "UtilsFeatureMatch",
                    argv.image,
                    pipeline_override={
                        "UtilsFeatureMatch": {
                            "recognition": {
                                "param": {"template": str(tpl_rel)}
                            }
                        }
                    }
                )

                if reco_result and reco_result.hit and reco_result.filtered_results:
                    for fr in reco_result.filtered_results:
                        box = [fr.box[0], fr.box[1], fr.box[2], fr.box[3]]
                        count = fr.count if hasattr(fr, 'count') else 0
                        print(f"[DEBUG] Hit: {tpl_rel}，Box: {box}, Count: {count}")
                        all_hits.append({
                            "template": str(tpl_rel),
                            "skin": extract_skin_from_template(str(tpl_rel)),
                            "box": box,
                            "count": count,
                        })
                else:
                    print(f"[DEBUG] 未找到匹配项: {tpl_rel}")

            if all_hits:
                # 第二步：按 box 位置聚类，近似的 box 归为同一个对象位置
                clusters = []  # 每个 cluster 是一组 box 近似的 hits
                for hit in all_hits:
                    placed = False
                    for cluster in clusters:
                        # 用 cluster 中第一个 hit 的 box 作为参考点
                        if _boxes_similar(cluster[0]["box"], hit["box"]):
                            cluster.append(hit)
                            placed = True
                            break
                    if not placed:
                        clusters.append([hit])

                print(f"[DEBUG] Distinct object positions: {len(clusters)}")

                # 第三步：每个 cluster（对象位置）内选 count 最高的 template 作为该 res
                results = []
                for cluster in clusters:
                    best_hit = max(cluster, key=lambda x: x["count"])
                    results.append(best_hit)

                # 按 count 降序排列
                results.sort(key=lambda x: x["count"], reverse=True)

                if len(results) > 1:
                    # 图片中有多个不同位置的对象
                    multi_detail = {}
                    for idx, r in enumerate(results):
                        multi_detail[f"res_{idx}"] = {
                            "skin": r["skin"],
                            "path": r["template"],
                            "box": r["box"],
                            "name": char_name,
                            "id": char_id,
                            "count": r["count"],
                            "iffriend": False
                        }
                    return CustomRecognition.AnalyzeResult(
                        box=[0, 0, 0, 0],
                        detail=multi_detail
                    )
                else:
                    # 图片中只有一个对象位置
                    r = results[0]
                    return CustomRecognition.AnalyzeResult(
                        box=r["box"],
                        detail={
                            "skin": r["skin"],
                            "path": r["template"],
                            "name": char_name,
                            "id": char_id,
                            "iffriend": False
                        }
                    )
            else:
                print("[DEBUG] 未找到任何匹配项")

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
                    "name": ar_name,
                     } if match_detail and match_detail.box and ar_mode else None
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
        
        if not avatar or not avatar.hit:
            print(f"[DEBUG] Failed to find character: {param['name']} {param['id']}")
            return CustomRecognition.AnalyzeResult(box=None, detail={})
        
        # 获取详细信息，best_result.detail 可能是 dict 或 JSON 字符串
        detail_dict = {}
        if avatar.best_result and avatar.best_result.detail:
            raw_detail = avatar.best_result.detail
            if isinstance(raw_detail, dict):
                detail_dict = raw_detail
            elif isinstance(raw_detail, str):
                try:
                    detail_dict = json.loads(raw_detail)
                except (json.JSONDecodeError, TypeError):
                    detail_dict = {}
            print(f"[DEBUG] detail_dict keys: {list(detail_dict.keys())}")
        
        # 判断是否为多结果（特征：box 为 [0,0,0,0]）
        is_multi = (avatar.box[0] == 0 and avatar.box[1] == 0
                    and avatar.box[2] == 0 and avatar.box[3] == 0)

        # ===== 内部辅助函数：对单个 ROI 执行 OCR 并填充结果到 entry =====
        def _fill_ocr(entry, ROI):
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
                                entry["Level"] = levres[0]
                                print(f"Found Level: {levres[0]} for character {param['name']} {param['id']}")
                                break
                        continue
                    elif match_mgr.fuzzy_match(text.text, ["Skill/S.A.Lv", "SkilI/S.A.Lv"], 0.8):
                        for num in nums:
                            if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                                skillres = [int(temp) for temp in num.text.split("/")]
                                entry["Skill"] = skillres[0]
                                entry["S.A.Lv"] = skillres[1]
                                print(f"Found Skill: {skillres[0]} and S.A.Lv: {skillres[1]} for character {param['name']} {param['id']}")
                                break
                        continue
                    elif match_mgr.fuzzy_match(text.text, "HP", 0.8):
                        for num in nums:
                            if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                                hpres = int(num.text)
                                entry["HP"] = hpres
                                print(f"Found HP: {hpres} for character {param['name']} {param['id']}")
                                break
                        continue
                    elif match_mgr.fuzzy_match(text.text, "ATK", 0.8):
                        for num in nums:
                            if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                                atkres = int(num.text)
                                entry["ATK"] = atkres
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
                entry["SLevel"] = int(texts[0].text)
                print(f"[DEBUG] Found Seed Level: {texts[0].text} for character {param['name']} {param['id']}")
                entry["SSkill"] = int(texts[1].text)
                print(f"[DEBUG] Found Seed Skill: {texts[1].text} for character {param['name']} {param['id']}")
                entry["SHP"] = int(texts[2].text)
                print(f"[DEBUG] Found Seed HP: {texts[2].text} for character {param['name']} {param['id']}")
                entry["SATK"] = int(texts[3].text)
                print(f"[DEBUG] Found Seed ATK: {texts[3].text} for character {param['name']} {param['id']}")

        def _fill_ar(entry):
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
                entry["AR"] = {
                    "name": ar_name,
                    "matched": bool(ar_result and ar_result.box)
                }
                print(f"[DEBUG] AR recognition for {ar_name}: {'matched' if ar_result and ar_result.box else 'not matched'}")
            else:
                print("[DEBUG] No AR specified, skipping AR recognition.")

        # ===== 多结果模式 =====
        if is_multi:
            multi_output = {}
            for res_key in sorted(detail_dict.keys()):
                if not res_key.startswith("res_"):
                    continue
                res_val = detail_dict[res_key]
                res_box = res_val.get("box", [0, 0, 0, 0])
                ROI = [res_box[0] - self.ROI[0], res_box[1] - self.ROI[1], self.ROI[2], self.ROI[3]]
                print(f"[DEBUG] Multi-result {res_key}: ROI={ROI}, box={res_box}")

                # 格式: charname/id/res_\d/entry
                entry = {
                    "Level": param.get("Level", self.DEAFAULT_PARAM_A["Level"] if template_type == "A" else None),
                    "SLevel": param.get("SLevel", self.DEAFAULT_PARAM_B["SLevel"] if template_type == "B" else None),
                    "Skill": param.get("Skill", self.DEAFAULT_PARAM_A["Skill"] if template_type == "A" else None),
                    "SSkill": param.get("SSkill", self.DEAFAULT_PARAM_B["SSkill"] if template_type == "B" else None),
                    "S.A.Lv": param.get("S.A.Lv", self.DEAFAULT_PARAM_B["S.A.Lv"] if template_type == "B" else self.DEAFAULT_PARAM_A["S.A.Lv"]),
                    "ATK": param.get("ATK", self.DEAFAULT_PARAM_A["ATK"] if template_type == "A" else None),
                    "SATK": param.get("SATK", self.DEAFAULT_PARAM_B["SATK"] if template_type == "B" else None),
                    "HP": param.get("HP", self.DEAFAULT_PARAM_A["HP"] if template_type == "A" else None),
                    "SHP": param.get("SHP", self.DEAFAULT_PARAM_B["SHP"] if template_type == "B" else None),
                    "AR": {"name": param.get("AR", None), "matched": True},
                    "iffriend": True,
                    "path": res_val.get("path"),
                    "skin": res_val.get("skin"),
                    "box": res_box,
                }

                _fill_ocr(entry, ROI)
                _fill_ar(entry)
                multi_output[res_key] = entry

            return CustomRecognition.AnalyzeResult(
                box=[0, 0, 0, 0],
                detail={param["name"]: {param["id"]: multi_output}}
            )

        # ===== 单结果模式（保留原有逻辑）=====
        output[param["name"]][param["id"]]["path"] = detail_dict.get("path") if detail_dict else None
        
        if detail_dict:
            print(f"[DEBUG] found character: {detail_dict.get('name')} {detail_dict.get('id')} at {avatar.box}, path: {detail_dict.get('path')}")
        if avatar.box:
            ROI = [avatar.box[0]-self.ROI[0], avatar.box[1]-self.ROI[1], self.ROI[2], self.ROI[3]] # 块
            print(f"[DEBUG] ROI for character {param['name']} {param['id']}: {ROI}")
        else:
            return CustomRecognition.AnalyzeResult(box=None, detail=param)
        
        _fill_ocr(output[param["name"]][param["id"]], ROI)
        _fill_ar(output[param["name"]][param["id"]])
        
        return CustomRecognition.AnalyzeResult(
            box=ROI if avatar and avatar.box else None,
            detail=output if avatar and avatar.box else None
        )