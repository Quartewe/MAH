from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
import json
import re
from pathlib import Path
from utils import data_io, match_mgr, proj_path


@AgentServer.custom_recognition("TraverseMatch")
class TraverseMatch(CustomRecognition):
    """
    遍历文件夹下的所有png模板, 支持输出所有匹配对象以及其对应的最可能模板
    
    Args:
        pipeline输入参数要求:
        {
            对角色识别:至少包含"name":str "id":int 键
            对AR识别:至少包含"AR":{"name":str} 键
        }
    Returns:
    若为单对象则box返回为对应的位置，detail返回为该对象最可能的模板路径
    {
        box=[x,y,w,h],
        detail={
            "skin": r["skin"],
            "path": r["template"],
            "name": char_name,
            "id": char_id,
            "iffriend": False
        }
    }

    若为多对象则box返回[0,0,1,1]，detail返回为一个字典，包含每个对象的位置信息和最可能的模板路径
     {
        "box": [0, 0, 1, 1],
        "detail": {
            "res_0": {
            "template": str(tpl_rel),
            "skin": extract_skin_from_template(str(tpl_rel)),
            "box": box,
            "count": count
            }
        }
    }
    若未识别到则box返回None,detail返回None
    """
    def __init__(self):
        super().__init__()
        self.BASE_PATH = self._detect_image_base_dir()
        self.CHAR_DATA = data_io.read_data(proj_path.CHAR_FILE)
        self.CHAR_LOWSTAR_DATA = data_io.read_data(proj_path.CHAR_LOWSTAR_FILE)
        self.AR_DATA = data_io.read_data(proj_path.AR_FILE)
        self.ELEMENTS = ["all", "dark", "evil", "fire", "god", "hero", "infinity", "light", "none", "water", "wood", "world"]

    def _detect_image_base_dir(self) -> Path:
        candidates = [
            proj_path.RESOURCE_DIR / "base" / "image",
            proj_path.PROJECT_ROOT / "resource" / "base" / "image",
            proj_path.PROJECT_ROOT / "assets" / "resource" / "base" / "image",
            proj_path.IMAGE_DIR,
            proj_path.RESOURCE_DIR / "image",
            proj_path.PROJECT_ROOT / "resource" / "image",
            proj_path.PROJECT_ROOT / "assets" / "resource" / "image",
        ]

        for candidate in candidates:
            if candidate.exists():
                print(f"[DEBUG] TraverseMatch 图片根目录: {candidate}")
                return candidate

        fallback = candidates[0]
        print(f"[ERROR] 未找到 TraverseMatch 图片根目录，回退到: {fallback}")
        return fallback

    def _resolve_image_path(self, raw_path):
        if not raw_path:
            return None

        path_str = str(raw_path).replace("\\", "/").lstrip("./")

        removable_prefixes = [
            "assets/resource/base/image/",
            "resource/base/image/",
            "assets/resource/image/",
            "resource/image/",
        ]
        for prefix in removable_prefixes:
            if path_str.startswith(prefix):
                path_str = path_str[len(prefix):]
                break

        try:
            image_root_rel = self.BASE_PATH.relative_to(proj_path.PROJECT_ROOT).as_posix()
            prefix = f"{image_root_rel}/"
            if path_str.startswith(prefix):
                path_str = path_str[len(prefix):]
        except ValueError:
            pass

        path_obj = Path(path_str)
        if path_obj.is_absolute():
            return path_obj

        return self.BASE_PATH / path_obj

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        # 处理 custom_recognition_param，MAA 框架会自动转换为 JSON 字符串或字典
        param_raw = argv.custom_recognition_param
        param = {}
        
        # 如果是字符串，进行 JSON 解析
        if isinstance(param_raw, str):
            if param_raw:
                try:
                    param = json.loads(param_raw)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"[ERRROR] JSON 解析失败: {e}")
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
        lowstar_mode = False
        ar_mode = False
        ar_name = None
        char_element = None
        
        print(f"[DEBUG] 角色名: {char_name}, 角色ID: {char_id}")

        # 低星模式优先：有角色名、无角色ID、且提供了合法 element
        if char_name and not char_id:
            char_element = param.get("element", None)
            if char_element and char_element in self.ELEMENTS:
                lowstar_mode = True
            else:
                print(f"[ERROR] 低星角色未提供有效属性({char_element})")
                return CustomRecognition.AnalyzeResult(box=None, detail=None)

        if lowstar_mode:
            template_path = self._resolve_image_path(
                self.CHAR_LOWSTAR_DATA.get(char_name, {}).get(char_element, {}).get("path", "").strip().strip('"').strip("'")
            )
        elif char_name and char_id:
            template_path = self._resolve_image_path(
                self.CHAR_DATA[char_name][char_id]["path"].strip().strip('"').strip("'")
            )
        else:
            # 回退到 AR 模式：仅当无法走角色识别时尝试
            ar_mode = True
            ar_name = param.get("AR", None)
            if ar_name:
                if ar_name in self.AR_DATA:
                    ar_data = self.AR_DATA.get(ar_name, {})
                    ar_raw_path = ar_data.get("path") or param.get("path")
                    template_path = self._resolve_image_path(ar_raw_path)
                else:
                    print(f"[DEBUG] 无效的 AR 名称: {ar_name}")
                    return CustomRecognition.AnalyzeResult(box=None, detail=None)
            else:
                print("[DEBUG] 未提供有效的 AR 数据")
                return CustomRecognition.AnalyzeResult(box=None, detail=None)
        
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
                print(f"[DEBUG] 正在查找角色模板: {tpl_rel}")
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
                        if count <= 10 or fr.box[0] == 0:
                            print(f"[DEBUG] {tpl_rel} 结果无效，跳过")
                            continue
                        print(f"[DEBUG] 命中模板: {tpl_rel}，位置: {box}, 计数: {count}")
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

                print(f"[DEBUG] 去重后对象位置数量: {len(clusters)}")

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
                        box=[0, 0, 1, 1],
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
            try:
                template = template_path.relative_to(self.BASE_PATH)
            except ValueError:
                template = Path(str(template_path).replace("\\", "/"))
            print(f"[DEBUG] 正在查找 AR: {template}")
            match_detail = context.run_recognition_direct(
                "FeatureMatch",
                {"template": str(template)},
                argv.image
                )
  
            if match_detail.box:
                print(f"[DEBUG] 找到 AR: {template}，位置: {match_detail.box}")
        
        else:
            print(f"[DEBUG] 模板路径不存在: {template_path}")
        
        return CustomRecognition.AnalyzeResult(
            box=match_detail.box if match_detail and match_detail.box else None,
            detail={"path": str(template),
                    "name": ar_name,
                     } if match_detail and match_detail.box and ar_mode else None
        )
    
@AgentServer.custom_recognition("GroupAvatarInfo")
class GroupAvatarInfo(CustomRecognition):
    """
    助战界面识别对应的角色信息并打包输出,支持同画面有多个角色

    Args:
        pipeline输入参数要求:
        {
            "template_type": str, #模板类型，A或B，决定默认参数的使用, A为常规界面，B为种子界面
            "name": str, #角色名 (若不输入默认为物部匡真)
            "id": int,   #角色id (若不输入默认为2，即匡真2卡)
            "Level": int, #角色等级（可选，默认为70）
            "SLevel": int, #种子等级（可选，默认为0，表示不识别种子）
            "S.A.Lv": int, #宝具等级（可选，默认为1）
            "Skill": int, #技能等级（可选，默认为100）
            "SSkill": int, #种子技能等级（可选，默认为0，表示不识别种子）
            "ATK": int, #攻击力（可选，默认为0，表示不识别）
            "SATK": int, #种子攻击力（可选，默认为0，表示不识别种子）
            "HP": int, #生命值（可选，默认为0，表示不识别）
            "SHP": int, #种子生命值（可选，默认为0，表示不识别种子）
            "AR": {       #如果要求对应ar识别则输入AR字段
                "name": str
            }
        }
        
    Returns:
        若为单对象则box返回为对应的位置，detail返回为该对象的识别信息
        若为多对象则box返回[0,0,1,1]，detail返回为一个字典
        若未识别到则box返回None, detail返回None
    """
    def __init__(self):
        super().__init__()
        self.ROI = [456, 21 , 965, 155] #块
        self.DEAFAULT_PARAM_A = {
            "name": "kyouma",
            "id": 2,
            "Level": 70,
            "S.A.Lv": 1,
            "Skill": 100,
            "ATK": 0,
            "HP": 0,
            "AR": None,
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
            "AR": None,
            "iffriend": True
        }
    
    
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        param = json.loads(argv.custom_recognition_param)
        
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
            if param.get("Level") or param.get("ATK") or param.get("HP") or param.get("Skill"):
                template_type =  "A"
            elif param.get("SLevel") or param.get("SATK") or param.get("SHP") or param.get("SSkill"):
                template_type = "B"
            else:                
                template_type = "A"
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
        
        # 统一处理 avatar.box：转换为 list 格式
        avatar_box = None
        if avatar and avatar.hit and avatar.box:
            try:
                avatar_box = [avatar.box[0], avatar.box[1], avatar.box[2], avatar.box[3]]
            except (IndexError, TypeError):
                avatar_box = None
        
        if not avatar or not avatar.hit or avatar_box is None:
            print(f"[DEBUG] 未找到角色: {param['name']} {param['id']}")
            return CustomRecognition.AnalyzeResult(box=None, detail=None)
        
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
            print(f"[DEBUG] detail_dict 键列表: {list(detail_dict.keys())}")
        
        # 判断是否为多结果（特征：box 为 [0,0,1,1]）
        is_multi = (avatar_box[0] == 0 and avatar_box[1] == 0
                and avatar_box[2] == 1 and avatar_box[3] == 1)

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
                                print(f"识别到等级: {levres[0]}，角色 {param['name']} {param['id']}")
                                break
                        continue
                    elif match_mgr.fuzzy_match(text.text, ["Skill/S.A.Lv", "SkilI/S.A.Lv"], 0.8):
                        for num in nums:
                            if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                                skillres = [int(temp) for temp in num.text.split("/")]
                                entry["Skill"] = skillres[0]
                                entry["S.A.Lv"] = skillres[1]
                                print(f"识别到技能: {skillres[0]}，S.A.Lv: {skillres[1]}，角色 {param['name']} {param['id']}")
                                break
                        continue
                    elif match_mgr.fuzzy_match(text.text, "HP", 0.8):
                        for num in nums:
                            if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                                hpres = int(num.text)
                                entry["HP"] = hpres
                                print(f"识别到 HP: {hpres}，角色 {param['name']} {param['id']}")
                                break
                        continue
                    elif match_mgr.fuzzy_match(text.text, "ATK", 0.8):
                        for num in nums:
                            if (num.box[0] - text.box[0]) in range(90,105) and (num.box[1] - text.box[1]) in range(-5,5):
                                atkres = int(num.text)
                                entry["ATK"] = atkres
                                print(f"识别到 ATK: {atkres}，角色 {param['name']} {param['id']}")
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
                print(f"[DEBUG] 识别到种子等级: {texts[0].text}，角色 {param['name']} {param['id']}")
                entry["SSkill"] = int(texts[1].text)
                print(f"[DEBUG] 识别到种子技能: {texts[1].text}，角色 {param['name']} {param['id']}")
                entry["SHP"] = int(texts[2].text)
                print(f"[DEBUG] 识别到种子 HP: {texts[2].text}，角色 {param['name']} {param['id']}")
                entry["SATK"] = int(texts[3].text)
                print(f"[DEBUG] 识别到种子 ATK: {texts[3].text}，角色 {param['name']} {param['id']}")

        def _fill_ar(entry):
            if param.get("AR"):
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
                print(f"[DEBUG] AR 识别结果 {ar_name}: {'匹配' if ar_result and ar_result.box else '未匹配'}")
            else:
                print("[DEBUG] 未指定 AR，跳过 AR 识别")

        # ===== 多结果模式 =====
        if is_multi:
            multi_output = {}
            for res_key in detail_dict.keys():
                if not res_key.startswith("res_"):
                    continue
                res_val = detail_dict[res_key]
                res_box = res_val.get("box", [0, 0, 1, 1])
                ROI = [res_box[0] - self.ROI[0], res_box[1] - self.ROI[1], self.ROI[2], self.ROI[3]]
                print(f"[DEBUG] 多结果 {res_key}: ROI={ROI}, box={res_box}")

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
                    "skin": res_val.get("skin")
                    ,"box": res_box
                }

                _fill_ocr(entry, ROI)
                _fill_ar(entry)
                multi_output[res_key] = entry

            return CustomRecognition.AnalyzeResult(
                box=[0, 0, 1, 1],
                detail={param["name"]: {param["id"]: multi_output}}
            )

        # ===== 单结果模式（保留原有逻辑）=====
        single_entry = {
            "Level": output[param["name"]][param["id"]]["Level"],
            "SLevel": output[param["name"]][param["id"]]["SLevel"],
            "Skill": output[param["name"]][param["id"]]["Skill"],
            "SSkill": output[param["name"]][param["id"]]["SSkill"],
            "S.A.Lv": output[param["name"]][param["id"]]["S.A.Lv"],
            "ATK": output[param["name"]][param["id"]]["ATK"],
            "SATK": output[param["name"]][param["id"]]["SATK"],
            "HP": output[param["name"]][param["id"]]["HP"],
            "SHP": output[param["name"]][param["id"]]["SHP"],
            "AR": output[param["name"]][param["id"]]["AR"],
            "iffriend": output[param["name"]][param["id"]]["iffriend"],
            "path": detail_dict.get("path") if detail_dict else None,
            "box": avatar_box
        }
        
        if detail_dict:
            print(f"[DEBUG] 找到角色: {detail_dict.get('name')} {detail_dict.get('id')}，位置: {avatar_box}, 路径: {detail_dict.get('path')}")
        
        # 用 avatar_box 计算 ROI
        ROI = [avatar_box[0]-self.ROI[0], avatar_box[1]-self.ROI[1], self.ROI[2], self.ROI[3]]
        print(f"[DEBUG] 角色 {param['name']} {param['id']} 的 ROI: {ROI}")
        
        _fill_ocr(single_entry, ROI)
        _fill_ar(single_entry)
        
        output[param["name"]][param["id"]] = {"res_0": single_entry}

        return CustomRecognition.AnalyzeResult(
            box=ROI,
            detail=output
        )
