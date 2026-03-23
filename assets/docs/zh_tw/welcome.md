# MAH

## 免責聲明

- 本資源 開源 且 免費
- 本資源按 "現狀" 提供，不附帶任何形式的明示或暗示擔保。使用者需 自行承擔所有風險。
- 作者不對因使用本資源而導致的任何直接、間接或結果性損失承擔責任。
- 本資源為 獨立組件，其 MIT 許可證不傳染，也不受與之集成的其他軟件許可證的影響。
- 基於本資源進行的任何 商業行為均與原作者無關，使用者 不得暗示任何官方關聯或認可。

## 歡迎使用MAH, 下面是使用指南

1. 本項目**只支持**安卓模擬器, 下面是配置要求:
    - 屏幕比例為16:9，推薦（以及最低）分辨率為 `1280x720`，不符合要求造成的運行報錯將不會被解決。

2. 完整 MAH 軟件壓縮包命名格式為 "MAH-平台-架構-版本.zip"，其餘均為無法單獨使用的“零部件”，請仔細閱讀。
在大部分情況下，您需要使用 x64 架構的 MAH，即您需要下載`MAH-win-x86_64-vXXX.zip`，而非`MAH-win-aarch64-vXXX.zip`。

## 功能介紹

### 啟動遊戲

啟動遊戲並等待進入主界面。

### 地城作戰

進行地城作戰，包括以下選項：

- 關卡選擇：支持所有常駐地城，活動地城支持且推薦手動填寫部分關鍵詞

- 挑戰次數：指定挑戰次數，如果超出現有DP且未填寫使用燈油則會刷到DP耗盡

- 使用燈油：自動使用燈油

- 選擇隊伍：填入對應的隊伍ID, 即每個隊伍欄左上角的那個`team X`

- 從`JSON`文件導入內容：支持從規範的`JSON`文件中讀取內容，詳細規範見docs/`自動戰鬥json配置.md`

  - 從`JSON`文件中自動獲取：從單一文件中獲取所有戰鬥相關數據

  - 自定義選擇組合：從不同文件中獲取戰鬥相關數據

#### 自定義選擇助戰角色

- 基礎信息：

  1. 角色名稱（**必填**）：要求為角色的內部英文名（大部分與官方英文名相同）下列出幾個特殊的例子，其他詳細內容請查找`JSON`字典索引，在文檔的最後將列出[`查找方式`](#相關內容查找方式)：
  
      - 煙神：**the**smokygod
      - 勇者：**the**hero
      - 主角：player

  2. 角色ID（**必填**）: 即是該角色的第幾張卡

  3. 神器等級（**可選**）

  4. AR卡（**可選**）：要求為AR卡內部英文名（**不為官方名稱**）詳細內容請查找`JSON`字典索引，在文檔的最後將列出[`查找方式`](#相關內容查找方式)。

- 篩選助戰（**可選**）：不填寫則自動選擇`絕對數值`最高的：

  - 數值篩選：即篩選實際展示給玩家的數值

  - 種子篩選：即篩選角色的種子相關數值

- 自動配隊：同`從JSON文件導入內容`

- 選擇戰鬥列表：同`從JSON文件導入內容`

### 體力作戰

大部分屬性與地城作戰相同，下列出存在差異的選項：

- 關卡選擇：支持14章花本，3個常駐日常任務，活動關卡支持且`推薦`手動填寫部分關鍵詞

  - 自定義每日任務：即從日常任務中手動輸入`相關關鍵詞`來進行選擇，可填充屬性為，下以`突破界限的試煉·天（3）`舉例：

    1. 自定義關卡名稱：支持且`推薦`手動填寫部分關鍵詞（關卡名稱:`天`）

    2. 難度關鍵詞：支持且`推薦`手動填寫部分關鍵詞（關卡難度:`（3）`）

- 使用體力藥：使用順序為`全`->`半`->`微`

### 領取獎勵

自動領取周常任務以及禮物中的內容

## 相關內容查找方式

**便捷查找插件正在銳意開發中**

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

***如果助戰填入的是低星角色請不要填入id***

`characters_lowstar.json` 的結構與 `characters.json` 類似，但低星角色（2星以下）可能存在 **weapon 為 `varies`** 的情況，即不同屬性對應不同武器：

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
