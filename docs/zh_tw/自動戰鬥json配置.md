# 自動戰鬥 JSON 規範

## 目錄

- [文件位置](#文件位置)
- [語法規範](#語法規範)
  - [team — 隊伍配置](#team)
  - [fight — 戰鬥配置](#fight)
- [角色及 AR 名獲取](#角色及-ar-名獲取)

---

## 文件位置

請將 JSON 文件放入 `data/auto_combat/` 文件夾中：

```
MAH/data/auto_combat/<文件名>.json
```

支持嵌套文件夾：

```
MAH/data/auto_combat/abc/cde/<文件名>.json
```

程序會自動遞歸遍歷 `auto_combat/` 下所有子目錄查找匹配的文件名。

---

## 語法規範

### 基本結構

每個 JSON 文件**必須**包含以下兩個根級屬性：

| 屬性 | 類型 | 必需 | 說明 |
|------|------|:----:|------|
| [`team`](#team) | `object` | ✅ | 隊伍配置 |
| [`fight`](#fight) | `object` | ✅ | 戰鬥配置 |

**完整結構概覽：**

```json
{
    "team": { ... },
    "fight": { ... }
}
```

---

### "team"

`team` 對象用於配置戰鬥隊伍，包含各隊員的角色信息。

#### 隊伍槽位

`team` 中**至少**包含 `LEADER` 和 `SUPPORT`，**最多**包含以下 7 個槽位中的 6 個：

| 槽位 | 類型 | 必需 | 說明 |
|------|------|:----:|------|
| `LEADER` | `object` | ✅ | 隊長 |
| `2` | `object` | ❌ | 第 2 隊員 |
| `3` | `object` | ❌ | 第 3 隊員 |
| `4` | `object` | ❌ | 第 4 隊員 |
| `5` | `object` | ❌ | 第 5 隊員 |
| `6` | `object` | ❌ | 第 6 隊員 |
| `SUPPORT` | `object` | ✅ | 助戰角色（占用一個數字槽位）|

#### 角色對象格式

每個槽位對象**必須**滿足以下格式：

| 屬性 | 類型 | 必需 | 說明 |
|------|------|:----:|------|
| `name` | `str` | ✅ | 角色英文名，參見[`索引字典`](#角色及-ar-名獲取) |
| `id` | `int` | ✅ | 角色卡面序號，參見[`索引字典`](#角色及-ar-名獲取) |
| [`AR`](#ar) | `str` | ❌ | AR 卡文件名，參見[`索引字典`](#角色及-ar-名獲取) |
| `element` | `str` | 對[`一卡多類`](#characters_lowstar)必需 | 即同一名字多種屬性為必須, ⚠️且對非一卡多類角色為***不可選***⚠️ |

> ⚠️ 如果對非一卡多類角色填入了`element`屬性, 程序將會無法運行!!!

**示例：**

```json
"team": {
    "LEADER": {
        "name": "amduscias",
        "id": 3
    },
    "2": {
        "name": "sanzo",
        "id": 2
    },
    "3": {
        "name": "yig",
        "id": 2
    },
    "SUPPORT": {
        "name": "kyouma",
        "id": 2,
        "Level": 70,
        "S.A.Lv": 1,
        "Skill": 100,
        "ATK": 0,
        "HP": 0,
        "AR": null
    },
    "5": {
        "name": "maneki",
        "id": 1
    },
    "6": {
        "name": "player",
        "id": 1
    }
}
```

#### SUPPORT 特殊規則

`SUPPORT` 會**取代**一個數字槽位（`2`~`6`）：

- `SUPPORT` 的位置決定它取代哪個槽位（上例中 `SUPPORT` 位於第 4 位，即取代 `4`）
- 若未取代任何數字槽位，則默認取代 `6`
  - 若只填入部分純數字對象, 就會取代**最後**一個`數字對象`的**下一個**`數字對象`, 如

    ```json
    {
        "LEADER":{ ... },
        "2":{ ... },
        "SUPPORT":{ ... }
    }
    ```

    就會取代`3`號位
- 支持將 `SUPPORT` 放在任意位置，但非標準位置會降低運行效率(而且不好看)

**`SUPPORT` 專屬額外屬性** — 用於設定助戰角色的篩選要求，優先選擇[`角色屬性最高`](#角色屬性選擇)的, 不填則不做要求：

| 屬性 | 類型 | 說明 |
|------|------|------|
| `Level` | `int` | 角色真實等級 |
| `SLevel` | `int` | 角色種子等級 |
| `Skill` | `int` | 角色真實技能等級 |
| `SSkill` | `int` | 角色種子技能等級 |
| `S.A.Lv` | `int` | 角色寶具等級 |
| `ATK` | `int` | 角色真實攻擊力 |
| `SATK` | `int` | 角色種子攻擊力 |
| `HP` | `int` | 角色真實生命值 |
| `SHP` | `int` | 角色種子生命值 |

目前暫時不支持檢查自有角色屬性

> ⚠️ **互斥規則：** 種子數值（`SLevel`/`SSkill`/`SATK`/`SHP`）與其對應的非種子數值互斥。若同時填入，該 JSON 文件**不會運行**。

##### 角色屬性選擇

支持在SUPPORT層的`select_mode`鍵中填入兩種屬性

| 屬性 | 類型 | 說明 |
|------|------|------|
| `best` | `str` | 見[`best選擇方式`](#best選擇方式) |
| `first` | `str` | 見[`first選擇方式`](#first選擇方式) |

若不填入`select_mode`鍵則默認為`best`

###### best選擇方式

- 選擇keywords中第一個關鍵詞的最大值

###### first選擇方式

- 優先從滿足條件的keywords中選出現最多的結果，如果都不滿足則從所有keywords中選出現最多的

部分源碼如下(如果你有更好的想法或想支持更多種選擇方式, 歡迎提issue)

```python
output = output_satisfied if output_satisfied else output_all

if mode == "first":
    most_common_data = output.get(keywords[0], None)
elif mode == "best":
    # 統計output中哪個 res_data 出現最多
    if output:
        id_counter = Counter(id(v) for v in output.values())
        best_id = id_counter.most_common(1)[0][0]
        most_common_data = next(v for v in output.values() if id(v) == best_id)
    else:
        most_common_data = None
else:
    most_common_data = None
```

---

### "fight"

`fight` 對象用於配置戰鬥中的行為序列

#### pos

`pos` 對象定義前 4 個角色（LEADER、2nd、3rd、4th）的初始位置。

**坐標系說明：**

- 以 **LEADER 所在格**為原點 `(0, 0)`
- **x 軸**：水平向右為正方向
- **y 軸**：豎直向下為正方向
- 僅考慮己方角色可到達的點

| 屬性 | 類型 | 說明 |
|------|------|------|
| `"1"` | `[x, y]` | LEADER 的位置 |
| `"2"` | `[x, y]` | 第 2 隊員的位置 |
| `"3"` | `[x, y]` | 第 3 隊員的位置 |
| `"4"` | `[x, y]` | 第 4 隊員的位置 |

**情況 0 示例：**

![sample](./sample_pic/3x3SIT0.png)

```json
"pos": {
    "1": [0, 0],
    "2": [1, 0],
    "3": [0, 1],
    "4": [1, 1]
}
```

**情況 1 示例：**

![sample](./sample_pic/3x3SIT1.png)

```json
"pos": {
    "1": [0, 0],
    "2": [1, 0],
    "3": [-1, 1],
    "4": [0, 1]
}
```

---

#### 動作對象

SIT 中的 `"0"`、`"1"`、... 以及 `loop` 內的每個子對象，均為**動作對象**。

每個動作對象**有且僅有**兩個屬性：

| 屬性 | 類型 | 說明 |
|------|------|------|
| `char` | `int` | 操作的角色編號，同 [`pos`](#pos) 中的 `1`~`4` |
| `action` | `list[str]` | 動作指令序列 |

**`action` 指令表：**

| 指令 | 方向 |
|:----:|------|
| `U` | 上 |
| `D` | 下 |
| `L` | 左 |
| `R` | 右 |
| `S` | 原地不動 |

**示例：**

```json
"0": {
    "char": 4,
    "action": ["L", "D", "R", "R", "U", "U"]
}
```

---

#### loop

`loop` 對象包含一組動作對象，從 `"0"` 開始編號，**循環執行**直到關卡結束。

**示例：**

```json
"loop": {
    "0": {
        "char": 1,
        "action": ["S"]
    },
    "1": {
        "char": 4,
        "action": ["S"]
    }
}
```

---

### 完整 JSON 示例

> 以下示例對應 `data/auto_combat/dungen_fight.json`

```json
{
    "team": {
        "LEADER": {
            "name": "amduscias",
            "id": 3
        },
        "2": {
            "name": "sanzo",
            "id": 2
        },
        "3": {
            "name": "yig",
            "id": 2
        },
        "SUPPORT": {
            "name": "kyouma",
            "id": 2,
            "Level": 70,
            "S.A.Lv": 1,
            "Skill": 100,
            "ATK": 0,
            "HP": 0,
            "AR": null
        },
        "5": {
            "name": "maneki",
            "id": 1
        },
        "6": {
            "name": "player",
            "id": 1
        }
    },
    "fight": {
        "pos": {
            "1": [0, 0],
            "2": [1, 0],
            "3": [0, 1],
            "4": [1, 1]
        },
        "0": {
            "char": 4,
            "action": ["U"]
        },
        "loop": {
            "0": { "char": 1, "action": ["S"] },
            "1": { "char": 4, "action": ["S"] }
        }
    }
}
```

---

## 角色及 AR 名獲取

<!-- 該條目預計在前端大更新後廢除 -->

角色名、ID 和 AR 卡名稱需要查閱 `MAH/docs` 下的索引字典：

| 文件 | 用途 |
|------|------|
| [`characters.json`](#characters) | 高星角色索引 |
| [`characters_lowstar.json`](#characters_lowstar) | 低星角色索引 |
| [`ar.json`](#ar) | AR 卡索引 |

> ⚠️ **請勿手動修改以上索引字典文件！**

---

### characters

`characters.json` 中每個角色以**英文名**為鍵，值為各卡面信息：

| 字段 | 類型 | 說明 | 可選值 |
|------|------|------|--------|
| `rarity` | `int` | 星級 | `1` ~ `5` |
| `element` | `str` | 屬性 | `water` `fire` `wood` `world` `light` `dark` `god` `hero` `evil` `all` `zero` `infinity` |
| `weapon` | `str` | 武器 | `slash` `thrust` `knock` `snipe` `shoot` `none` `magic` `longslash` |
| `path` | `str` | 資源路徑 | — |

**示例：**

```json
"shino": {
    "01": {
        "rarity": 3,
        "element": "evil",
        "weapon": "slash",
        "path": "assets/resource/image/character/shino/01"
    },
    "02": {
        "rarity": 5,
        "element": "evil",
        "weapon": "thrust",
        "path": "assets/resource/image/character/shino/02"
    }
}
```

---

### characters_lowstar

`characters_lowstar.json` 的結構與 `characters.json` 類似，但低星角色可能存在 **weapon 為 `varies`** 的情況，即不同屬性對應不同武器：

**示例：**

```json
"pirate": {
    "rarity": 1,
    "weapon": "varies",
    "dark": {
        "weapon": "slash",
        "path": "assets/resource/image/character/pirate/dark"
    },
    "earth": {
        "weapon": "thrust",
        "path": "assets/resource/image/character/pirate/earth"
    }
},
"ouroboros": {
    "rarity": 2,
    "weapon": "none",
    "all": {
        "path": "assets/resource/image/character/ouroboros/all"
    },
    "infinity": {
        "path": "assets/resource/image/character/ouroboros/infinity"
    },
    "zero": {
        "path": "assets/resource/image/character/ouroboros/zero"
    }
}
```

> 當 `weapon` 為 `varies` 時，需在各屬性子對象中分別指定 `weapon`。

---

### AR

`ar.json` 中每張 AR 卡以**文件名**為鍵：

| 字段 | 類型 | 說明 |
|------|------|------|
| `jp_rawname` | `str` | AR 卡日文名 |
| `rarity` | `int` | 星級（`1` ~ `5`） |
| `tag` | `list[str]` | 卡中出現的角色英文名 |
| `path` | `str` | 資源路徑 |

**示例：**

```json
"ar_shino_moritaka.png": {
    "jp_rawname": "犬どもの戦場",
    "rarity": 4,
    "tag": ["shino", "moritaka"],
    "path": "ar\\ar_shino_moritaka.png"
}
```