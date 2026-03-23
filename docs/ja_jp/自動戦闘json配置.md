# 自動戦闘 JSON 仕様

## 目次

- [ファイルの場所](#ファイルの場所)
- [構文仕様](#構文仕様)
  - [team — チーム構成](#team)
  - [fight — 戦闘構成](#fight)
- [キャラクターおよびAR名の取得](#キャラクターおよびAR名の取得)

---

## ファイルの場所

JSONファイルは `data/auto_combat/` フォルダに配置してください：

```
MAH/data/auto_combat/<ファイル名>.json
```

ネストされたフォルダもサポートされています：

```
MAH/data/auto_combat/abc/cde/<ファイル名>.json
```

プログラムは `auto_combat/` 下のすべてのサブディレクトリを自動的に再帰検索し、一致するファイル名を見つけます。

---

## 構文仕様

### 基本構造

各JSONファイルは以下の2つのルートレベルプロパティを**必ず**含める必要があります：

| プロパティ | 型 | 必須 | 説明 |
|------|------|:----:|------|
| [`team`](#team) | `object` | ✅ | チーム構成 |
| [`fight`](#fight) | `object` | ✅ | 戦闘構成 |

**全体構造の概要：**

```json
{
    "team": { ... },
    "fight": { ... }
}
```

---

### "team"

`team` オブジェクトは、各メンバーのキャラクター情報を含む戦闘チームを構成するために使用されます。

#### チームスロット

`team` には**少なくとも** `LEADER` と `SUPPORT` が含まれており、以下の7つのスロットのうち**最大**6つを含めることができます：

| スロット | 型 | 必須 | 説明 |
|------|------|:----:|------|
| `LEADER` | `object` | ✅ | リーダー |
| `2` | `object` | ❌ | 2番目のメンバー |
| `3` | `object` | ❌ | 3番目のメンバー |
| `4` | `object` | ❌ | 4番目のメンバー |
| `5` | `object` | ❌ | 5番目のメンバー |
| `6` | `object` | ❌ | 6番目のメンバー |
| `SUPPORT` | `object` | ✅ | サポートキャラクター（数字スロットを1つ占有します）|

#### キャラクターオブジェクトの形式

各スロットオブジェクトは**必ず**以下の形式を満たす必要があります：

| プロパティ | 型 | 必須 | 説明 |
|------|------|:----:|------|
| `name` | `str` | ✅ | キャラクターの英語名、[`インデックス辞書`](#キャラクターおよびAR名の取得)を参照 |
| `id` | `int` | ✅ | キャラクターカードのID、[`インデックス辞書`](#キャラクターおよびAR名の取得)を参照 |
| [`AR`](#ar) | `str` | ❌ | ARカードのファイル名、[`インデックス辞書`](#キャラクターおよびAR名の取得)を参照 |
| `element` | `str` | [`複数属性カード`](#characters_lowstar)の場合は必須 | 同じ名前で複数の属性を持つ場合は必須です。⚠️ 複数属性ではないキャラクターの場合は***記入不可***です ⚠️ |

> ⚠️ 複数属性ではないキャラクターに対して `element` 属性を記入した場合、プログラムは実行されません!!!

**例：**

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

#### SUPPORT の特別ルール

`SUPPORT` は数字スロット（`2`〜`6`）の1つを**置き換え**ます：

- `SUPPORT` の位置がどのスロットを置き換えるかを決定します（上の例では `SUPPORT` は4番目にあり、`4` を置き換えます）。
- どの数字スロットも置き換えない場合、デフォルトでスロット `6` を置き換えます。
  - 純粋な数字オブジェクトが一部しか入力されていない場合、**最後**の `数字オブジェクト` の**次**の `数字オブジェクト` を置き換えます。例：

    ```json
    {
        "LEADER":{ ... },
        "2":{ ... },
        "SUPPORT":{ ... }
    }
    ```

    この場合、`3` 番目のスロットを置き換えます。
- `SUPPORT` を任意の位置に配置することはサポートされていますが、標準的でない位置は実行効率を低下させます（見た目も良くありません）。

**`SUPPORT` 専用の追加属性** — サポートキャラクターの絞り込み条件を設定するために使用され、[`キャラクター属性の最高値`](#キャラクター属性の選択)を持つものを優先的に選択します。未入力の場合は条件を指定しません：

| 属性 | 型 | 説明 |
|------|------|------|
| `Level` | `int` | キャラクターの実際のレベル |
| `SLevel` | `int` | キャラクターのシードレベル |
| `Skill` | `int` | キャラクターの実際のスキルレベル |
| `SSkill` | `int` | キャラクターのシードスキルレベル |
| `S.A.Lv` | `int` | キャラクターの神器レベル |
| `ATK` | `int` | キャラクターの実際の攻撃力 |
| `SATK` | `int` | キャラクターのシード攻撃力 |
| `HP` | `int` | キャラクターの実際のHP |
| `SHP` | `int` | キャラクターのシードHP |

現在、自分のキャラクターの属性をチェックすることはサポートされていません。

> ⚠️ **排他ルール：** シード値（`SLevel`/`SSkill`/`SATK`/`SHP`）は、対応する非シード値とは排他的です。同時に記入した場合、その JSON ファイルは**実行されません**。

##### キャラクター属性の選択

SUPPORT層の `select_mode` キーに2種類の属性を入力できます：

| 属性 | 型 | 説明 |
|------|------|------|
| `best` | `str` | [`best選択方式`](#best選択方式)を参照 |
| `first` | `str` | [`first選択方式`](#first選択方式)を参照 |

`select_mode` キーが入力されていない場合、デフォルトは `best` となります。

###### best選択方式

- `keywords` の中の最初のキーワードの最大値を選択します。

###### first選択方式

- 条件を満たす `keywords` の中から最も多く出現する結果を優先的に選択し、何も満たさない場合はすべての `keywords` の中から最も多く出現する結果を選択します。

一部のソースコードは以下の通りです（より良いアイデアがある場合や、他の選択方式をサポートしたい場合は、issue を提出してください）：

```python
output = output_satisfied if output_satisfied else output_all

if mode == "first":
    most_common_data = output.get(keywords[0], None)
elif mode == "best":
    # outputの中でどの res_data が最も多く出現するかを統計する
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

`fight` オブジェクトは、戦闘中の行動シーケンスを構成するために使用されます。

#### pos

`pos` オブジェクトは、最初の4キャラクター（LEADER、2nd、3rd、4th）の初期位置を定義します。

**座標系の説明：**

- **LEADER が配置されているマス**を原点 `(0, 0)` とします。
- **x軸**：水平右方向が正の方向です。
- **y軸**：垂直下方向が正の方向です。
- 味方キャラクターが移動可能なポイントのみが考慮されます。

| 属性 | 型 | 説明 |
|------|------|------|
| `"1"` | `[x, y]` | LEADERの位置 |
| `"2"` | `[x, y]` | 2番目のメンバーの位置 |
| `"3"` | `[x, y]` | 3番目のメンバーの位置 |
| `"4"` | `[x, y]` | 4番目のメンバーの位置 |

**状況0の例：**

![sample](./sample_pic/3x3SIT0.png)

```json
"pos": {
    "1": [0, 0],
    "2": [1, 0],
    "3": [0, 1],
    "4": [1, 1]
}
```

**状況1の例：**

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

#### アクションオブジェクト

SIT内の `"0"`, `"1"`, ... および `loop` 内の各サブオブジェクトは、すべて**アクションオブジェクト**です。

各アクションオブジェクトは以下の2つの属性を**必ず1つずつ**持ちます：

| 属性 | 型 | 説明 |
|------|------|------|
| `char` | `int` | 操作するキャラクターの番号、[`pos`](#pos) の `1`~`4` と同じ |
| `action` | `list[str]` | アクションコマンドのシーケンス |

**`action` コマンドリスト：**

| コマンド | 方向 |
|:----:|------|
| `U` | 上 |
| `D` | 下 |
| `L` | 左 |
| `R` | 右 |
| `S` | その場で待機 |

**例：**

```json
"0": {
    "char": 4,
    "action": ["L", "D", "R", "R", "U", "U"]
}
```

---

#### loop

`loop` オブジェクトは、レベルが終了するまで**繰り返し実行**されるアクションオブジェクトのセットを含み、`"0"` から番号付けされます。

**例：**

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

### 完全な JSON の例

> 以下の例は `data/auto_combat/dungen_fight.json` に対応しています

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

## キャラクターおよびAR名の取得

<!-- この項目はフロントエンドの大幅なアップデート後に廃止される予定です -->

キャラクター名、ID、ARカード名は、`MAH/docs` 以下のインデックス辞書を参照する必要があります：

| ファイル | 用途 |
|------|------|
| [`characters.json`](#characters) | 高レアリティキャラクターインデックス |
| [`characters_lowstar.json`](#characters_lowstar) | 低レアリティキャラクターインデックス |
| [`ar.json`](#ar) | ARカードインデックス |

> ⚠️ **上記のインデックス辞書ファイルを手動で変更しないでください！**

---

### characters

`characters.json` では、各キャラクターの**英語名**がキーとなり、値には各カードの情報が含まれます：

| フィールド | 型 | 説明 | 可能な値 |
|------|------|------|--------|
| `rarity` | `int` | 星（レアリティ） | `1` ~ `5` |
| `element` | `str` | 属性 | `water` `fire` `wood` `world` `light` `dark` `god` `hero` `evil` `all` `zero` `infinity` |
| `weapon` | `str` | 武器 | `slash` `thrust` `knock` `snipe` `shoot` `none` `magic` `longslash` |
| `path` | `str` | リソースパス | — |

**例：**

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

`characters_lowstar.json` の構造は `characters.json` と似ていますが、低レアリティのキャラクターは **weapon が `varies`** の場合があり、異なる属性が異なる武器に対応していることを意味します：

**例：**

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

> `weapon` が `varies` の場合、各属性の子オブジェクト内で個別に `weapon` を指定する必要があります。

---

### AR

`ar.json` では、各ARカードの**ファイル名**がキーとなります：

| フィールド | 型 | 説明 |
|------|------|------|
| `jp_rawname` | `str` | ARカードの日本語名 |
| `rarity` | `int` | 星（レアリティ）（`1` ~ `5`） |
| `tag` | `list[str]` | カードに登場するキャラクターの英語名 |
| `path` | `str` | リソースパス |

**例：**

```json
"ar_shino_moritaka.png": {
    "jp_rawname": "犬どもの戦場",
    "rarity": 4,
    "tag": ["shino", "moritaka"],
    "path": "ar\\ar_shino_moritaka.png"
}
```