# MAH

## 免责声明

- 本资源 开源 且 免费
- 本资源按 "现状" 提供，不附带任何形式的明示或暗示担保。使用者需 自行承担所有风险。
- 作者不对因使用本资源而导致的任何直接、间接或结果性损失承担责任。
- 本资源为 独立组件，其 MIT 许可证不传染，也不受与之集成的其他软件许可证的影响。
- 基于本资源进行的任何 商业行为均与原作者无关，使用者 不得暗示任何官方关联或认可。

## 欢迎使用MAH, 下面是使用指南

1. 本项目**只支持**安卓模拟器, 下面是配置要求:
    - 屏幕比例为16:9，推荐（以及最低）分辨率为 `1280x720`，不符合要求造成的运行报错将不会被解决。

2. 完整 MAH 软件压缩包命名格式为 "MAH-平台-架构-版本.zip"，其余均为无法单独使用的“零部件”，请仔细阅读。
在大部分情况下，您需要使用 x64 架构的 MAH，即您需要下载`MAH-win-x86_64-vXXX.zip`，而非`MAH-win-aarch64-vXXX.zip`。

## 功能介绍

### 启动游戏

启动游戏并等待进入主界面。

### 地城作战

进行地城作战，包括以下选项：

- 关卡选择：支持所有常驻地城，活动地城支持且推荐手动填写部分关键词

- 挑战次数：指定挑战次数，如果超出现有DP且未填写使用灯油则会刷到DP耗尽

- 使用灯油：自动使用灯油

- 选择队伍：填入对应的队伍ID, 即每个队伍栏左上角的那个`team X`

- 从`JSON`文件导入内容：支持从规范的`JSON`文件中读取内容，详细规范见docs/`自动战斗json配置.md`

  - 从`JSON`文件中自动获取：从单一文件中获取所有战斗相关数据

  - 自定义选择组合：从不同文件中获取战斗相关数据

#### 自定义选择助战角色

- 基础信息：

  1. 角色名称（**必填**）：要求为角色的内部英文名（大部分与官方英文名相同）下列出几个特殊的例子，其他详细内容请查找`JSON`字典索引，在文档的最后将列出[`查找方式`](#相关内容查找方式)：
  
      - 烟神：**the**smokygod
      - 勇者：**the**hero
      - 主角：player

  2. 角色ID（**必填**）: 即是该角色的第几张卡

  3. 神器等级（**可选**）

  4. AR卡（**可选**）：要求为AR卡内部英文名（**不为官方名称**）详细内容请查找`JSON`字典索引，在文档的最后将列出[`查找方式`](#相关内容查找方式)。

- 筛选助战（**可选**）：不填写则自动选择`绝对数值`最高的：

  - 数值筛选：即筛选实际展示给玩家的数值

  - 种子筛选：即筛选角色的种子相关数值

- 自动配队：同`从JSON文件导入内容`

- 选择战斗列表：同`从JSON文件导入内容`

### 体力作战

大部分属性与地城作战相同，下列出存在差异的选项：

- 关卡选择：支持14章花本，3个常驻日常任务，活动关卡支持且`推荐`手动填写部分关键词

  - 自定义每日任务：即从日常任务中手动输入`相关关键词`来进行选择，可填充属性为，下以`突破界限的试炼·天（3）`举例：

    1. 自定义关卡名称：支持且`推荐`手动填写部分关键词（关卡名称:`天`）

    2. 难度关键词：支持且`推荐`手动填写部分关键词（关卡难度:`（3）`）

- 使用体力药：使用顺序为`全`->`半`->`微`

### 领取奖励

自动领取周常任务以及礼物中的内容

## 相关内容查找方式

**便捷查找插件正在锐意开发中**

角色名、ID 和 AR 卡名称需要查阅 `MAH/docs` 下的索引字典：

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

***如果助战填入的是低星角色请不要填入id***

`characters_lowstar.json` 的结构与 `characters.json` 类似，但低星角色（2星以下）可能存在 **weapon 为 `varies`** 的情况，即不同属性对应不同武器：

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
