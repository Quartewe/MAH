# 自动战斗 JSON 规范

> **在阅读本文档前请确认：**
>
> - 确保你已经下载 **`release`** 中的 **`resource`** 文件夹并解压到对应的地址
> - ***请不要修改文档中提到的索引字典!!!***

## 目录

- [文件位置](#文件位置)
- [语法规范](#语法规范)
  - [team — 队伍配置](#team)
  - [fight — 战斗配置](#fight)
- [角色及 AR 名获取](#角色及-ar-名获取)

---

## 文件位置

请将 JSON 文件放入 `data/auto_combat/` 文件夹中：

```
MAH/data/auto_combat/<文件名>.json
```

支持嵌套文件夹：

```
MAH/data/auto_combat/abc/cde/<文件名>.json
```

程序会自动递归遍历 `auto_combat/` 下所有子目录查找匹配的文件名。

---

## 语法规范

### 基本结构

每个 JSON 文件**必须**包含以下两个根级属性：

| 属性 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| [`team`](#team) | `object` | ✅ | 队伍配置 |
| [`fight`](#fight) | `object` | ✅ | 战斗配置 |

**完整结构概览：**

```json
{
    "team": { ... },
    "fight": { ... }
}
```

---

### "team"

`team` 对象用于配置战斗队伍，包含各队员的角色信息。

#### 队伍槽位

`team` 中**至少**包含 `LEADER` 和 `SUPPORT`，**最多**包含以下 7 个槽位中的 6 个：

| 槽位 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `LEADER` | `object` | ✅ | 队长 |
| `2` | `object` | ❌ | 第 2 队员 |
| `3` | `object` | ❌ | 第 3 队员 |
| `4` | `object` | ❌ | 第 4 队员 |
| `5` | `object` | ❌ | 第 5 队员 |
| `6` | `object` | ❌ | 第 6 队员 |
| `SUPPORT` | `object` | ✅ | 助战角色（占用一个数字槽位）|

#### 角色对象格式

每个槽位对象**必须**满足以下格式：

| 属性 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `name` | `str` | ✅ | 角色英文名，参见[`索引字典`](#角色及-ar-名获取) |
| `id` | `int` | ✅ | 角色卡面序号，参见[`索引字典`](#角色及-ar-名获取) |
| [`AR`](#ar) | `str` | ❌ | AR 卡文件名，参见[`索引字典`](#角色及-ar-名获取) |
| `element` | `str` | 对[`一卡多类`](#characters_lowstar)必需 | 即同一名字多种属性为必须, ⚠️且对非一卡多类角色为***不可选***⚠️ |

> ⚠️ 如果对非一卡多类角色填入了`element`属性, 程序将会无法运行!!!

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

#### SUPPORT 特殊规则

`SUPPORT` 会**取代**一个数字槽位（`2`~`6`）：

- `SUPPORT` 的位置决定它取代哪个槽位（上例中 `SUPPORT` 位于第 4 位，即取代 `4`）
- 若未取代任何数字槽位，则默认取代 `6`
  - 若只填入部分纯数字对象, 就会取代**最后**一个`数字对象`的**下一个**`数字对象`, 如

    ```json
    {
        "LEADER":{ ... },
        "2":{ ... },
        "SUPPORT":{ ... }
    }
    ```

    就会取代`3`号位
- 支持将 `SUPPORT` 放在任意位置，但非标准位置会降低运行效率(而且不好看)

**`SUPPORT` 专属额外属性** — 用于设定助战角色的筛选要求，优先选择[`角色属性最高`](#角色属性选择)的, 不填则不做要求：

| 属性 | 类型 | 说明 |
|------|------|------|
| `Level` | `int` | 角色真实等级 |
| `SLevel` | `int` | 角色种子等级 |
| `Skill` | `int` | 角色真实技能等级 |
| `SSkill` | `int` | 角色种子技能等级 |
| `S.A.Lv` | `int` | 角色宝具等级 |
| `ATK` | `int` | 角色真实攻击力 |
| `SATK` | `int` | 角色种子攻击力 |
| `HP` | `int` | 角色真实生命值 |
| `SHP` | `int` | 角色种子生命值 |

目前暂时不支持检查自有角色属性

> ⚠️ **互斥规则：** 种子数值（`SLevel`/`SSkill`/`SATK`/`SHP`）与其对应的非种子数值互斥。若同时填入，该 JSON 文件**不会运行**。

##### 角色属性选择

支持在SUPPORT层的`select_mode`键中填入两种属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `best` | `str` | 见[`best选择方式`](#best选择方式) |
| `first` | `str` | 见[`first选择方式`](#first选择方式) |

若不填入`select_mode`键则默认为`best`

###### best选择方式

- 选择keywords中第一个关键词的最大值

###### first选择方式

- 优先从满足条件的keywords中选出现最多的结果，如果都不满足则从所有keywords中选出现最多的

部分源码如下(如果你有更好的想法或想支持更多种选择方式, 欢迎提issue)

```python
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
```

---

### "fight"

`fight` 对象用于配置战斗中的行为序列，至少包含一个 [`SIT`](#sit) 对象。

#### SIT

每个 SIT 代表一种战场局面（situation）下的行动方案。

**命名规范：**

SIT 名称**必须**为 `"SIT"` + 从 0 开始的连续整数，不可跳跃，不可重复，且**必须包含 `SIT0`**。

✅ 正确：

```json
"SIT0": { ... },
"SIT1": { ... }
```

❌ 错误 — 序号不连续：

```json
"SIT0": { ... },
"SIT114514": { ... }
```

❌ 错误 — 缺少 `SIT0`：

```json
"SIT1": { ... },
"SIT2": { ... }
```

**SIT 子属性：**

| 属性 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| [`pos`](#pos) | `object` | ✅ | 角色初始位置 |
| [`"0"`](#动作对象) | `object` | ✅ | 起始动作（第 1 步） |
| [`"1"`, `"2"`, ...](#动作对象) | `object` | ❌ | 后续动作步骤 |
| [`loop`](#loop) | `object` | ❌ | 循环动作，直到关卡完成 |

---

#### pos

`pos` 对象定义前 4 个角色（LEADER、2nd、3rd、4th）的初始位置。

**坐标系说明：**

- 以 **LEADER 所在格**为原点 `(0, 0)`
- **x 轴**：水平向右为正方向
- **y 轴**：竖直向下为正方向
- 仅考虑己方角色可到达的点

| 属性 | 类型 | 说明 |
|------|------|------|
| `"1"` | `[x, y]` | LEADER 的位置 |
| `"2"` | `[x, y]` | 第 2 队员的位置 |
| `"3"` | `[x, y]` | 第 3 队员的位置 |
| `"4"` | `[x, y]` | 第 4 队员的位置 |

**情况 0 示例：**

![sample](./sample_pic/3x3SIT0.png)

```json
"pos": {
    "1": [0, 0],
    "2": [1, 0],
    "3": [0, 1],
    "4": [1, 1]
}
```

**情况 1 示例：**

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

#### 动作对象

SIT 中的 `"0"`、`"1"`、... 以及 `loop` 内的每个子对象，均为**动作对象**。

每个动作对象**有且仅有**两个属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `char` | `int` | 操作的角色编号，同 [`pos`](#pos) 中的 `1`~`4` |
| `action` | `list[str]` | 动作指令序列 |

**`action` 指令表：**

| 指令 | 方向 |
|:----:|------|
| `U` | 上 |
| `D` | 下 |
| `L` | 左 |
| `R` | 右 |
| `S` | 原地不动 |

**示例：**

```json
"0": {
    "char": 4,
    "action": ["L", "D", "R", "R", "U", "U"]
}
```

---

#### loop

`loop` 对象包含一组动作对象，从 `"0"` 开始编号，**循环执行**直到关卡结束。

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

> 以下示例对应 `data/auto_combat/dungen_fight.json`

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
        "SIT0": {
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
        },
        "SIT1": {
            "pos": {
                "1": [0, 0],
                "2": [1, 0],
                "3": [-1, 1],
                "4": [0, 1]
            },
            "0": {
                "char": 4,
                "action": ["L", "D", "R", "R", "U", "U"]
            },
            "loop": {
                "0": { "char": 1, "action": ["S"] },
                "1": { "char": 4, "action": ["S"] }
            }
        }
    }
}
```

---

## 角色及 AR 名获取

<!-- 该条目预计在前端大更新后废除 -->

角色名、ID 和 AR 卡名称需要查阅 `MAH/assets/index` 下的索引字典：

| 文件 | 用途 |
|------|------|
| [`characters.json`](#characters) | 高星角色索引 |
| [`characters_lowstar.json`](#characters_lowstar) | 低星角色索引 |
| [`ar.json`](#ar) | AR 卡索引 |

> ⚠️ **请勿手动修改以上索引字典文件！**

---

### characters

`characters.json` 中每个角色以**英文名**为键，值为各卡面信息：

| 字段 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| `rarity` | `int` | 星级 | `1` ~ `5` |
| `element` | `str` | 属性 | `water` `fire` `wood` `world` `light` `dark` `god` `hero` `evil` `all` `zero` `infinity` |
| `weapon` | `str` | 武器 | `slash` `thrust` `knock` `snipe` `shoot` `none` `magic` `longslash` |
| `path` | `str` | 资源路径 | — |

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

`characters_lowstar.json` 的结构与 `characters.json` 类似，但低星角色可能存在 **weapon 为 `varies`** 的情况，即不同属性对应不同武器：

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

> 当 `weapon` 为 `varies` 时，需在各属性子对象中分别指定 `weapon`。

---

### AR

`ar.json` 中每张 AR 卡以**文件名**为键：

| 字段 | 类型 | 说明 |
|------|------|------|
| `jp_rawname` | `str` | AR 卡日文名 |
| `rarity` | `int` | 星级（`1` ~ `5`） |
| `tag` | `list[str]` | 卡中出现的角色英文名 |
| `path` | `str` | 资源路径 |

**示例：**

```json
"ar_shino_moritaka.png": {
    "jp_rawname": "犬どもの戦場",
    "rarity": 4,
    "tag": ["shino", "moritaka"],
    "path": "ar\\ar_shino_moritaka.png"
}
```
