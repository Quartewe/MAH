# Auto Combat JSON Specification

## Table of Contents

- [File Location](#file-location)
- [Syntax Specification](#syntax-specification)
  - [team — Team Configuration](#team)
  - [fight — Combat Configuration](#fight)
- [Character and AR Name Retrieval](#character-and-ar-name-retrieval)

---

## File Location

Please place the JSON files into the `data/auto_combat/` folder:

```
MAH/data/auto_combat/<filename>.json
```

Nested folders are supported:

```
MAH/data/auto_combat/abc/cde/<filename>.json
```

The program will automatically and recursively traverse all subdirectories under `auto_combat/` to find matching filenames.

---

## Syntax Specification

### Basic Structure

Each JSON file **must** contain the following two root-level properties:

| Property | Type | Required | Description |
|------|------|:----:|------|
| [`team`](#team) | `object` | ✅ | Team Configuration |
| [`fight`](#fight) | `object` | ✅ | Combat Configuration |

**Complete Structure Overview:**

```json
{
    "team": { ... },
    "fight": { ... }
}
```

---

### "team"

The `team` object is used to configure the combat team, containing character information for each team member.

#### Team Slots

`team` must contain **at least** `LEADER` and `SUPPORT`, and **at most** 6 of the following 7 slots:

| Slot | Type | Required | Description |
|------|------|:----:|------|
| `LEADER` | `object` | ✅ | Leader |
| `2` | `object` | ❌ | 2nd Member |
| `3` | `object` | ❌ | 3rd Member |
| `4` | `object` | ❌ | 4th Member |
| `5` | `object` | ❌ | 5th Member |
| `6` | `object` | ❌ | 6th Member |
| `SUPPORT` | `object` | ✅ | Support Character (occupies one numeric slot) |

#### Character Object Format

Each slot object **must** satisfy the following format:

| Property | Type | Required | Description |
|------|------|:----:|------|
| `name` | `str` | ✅ | Character English Name, see [`Index Dictionaries`](#character-and-ar-name-retrieval) |
| `id` | `int` | ✅ | Character Card ID, see [`Index Dictionaries`](#character-and-ar-name-retrieval) |
| [`AR`](#ar) | `str` | ❌ | AR Card Filename, see [`Index Dictionaries`](#character-and-ar-name-retrieval) |
| `element` | `str` | Required for [`multi-element cards`](#characters_lowstar) | Mandatory for characters with multiple elements under the same name. ⚠️ **NOT ALLOWED** for non-multi-element characters ⚠️ |

> ⚠️ If the `element` attribute is filled in for a non-multi-element character, the program will fail to run!!!

**Example:**

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

#### Special Rules for SUPPORT

`SUPPORT` will **replace** one numeric slot (`2`~`6`):

- The position of `SUPPORT` determines which slot it replaces (in the example above, `SUPPORT` is in the 4th position, replacing slot `4`).
- If no numeric slot is replaced, it defaults to replacing slot `6`.
  - If only partial numeric objects are filled in, it will replace the slot **after** the **last** `numeric object`. For example:

    ```json
    {
        "LEADER":{ ... },
        "2":{ ... },
        "SUPPORT":{ ... }
    }
    ```

    Here it will replace slot `3`.
- `SUPPORT` can be placed anywhere, but a non-standard position reduces execution efficiency (and doesn't look neat).

**`SUPPORT` Exclusive Additional Attributes** — Used to set screening criteria for the support character, prioritizing the one with the [`highest character stats`](#character-stat-selection). If left empty, no requirements are applied:

| Property | Type | Description |
|------|------|------|
| `Level` | `int` | Character's actual level |
| `SLevel` | `int` | Character's seed level |
| `Skill` | `int` | Character's actual skill level |
| `SSkill` | `int` | Character's seed skill level |
| `S.A.Lv` | `int` | Character's Sacred Artifact level |
| `ATK` | `int` | Character's actual ATK |
| `SATK` | `int` | Character's seed ATK |
| `HP` | `int` | Character's actual HP |
| `SHP` | `int` | Character's seed HP |

Checking your own character stats is temporarily unsupported.

> ⚠️ **Mutual Exclusivity Rule:** Seed values (`SLevel`/`SSkill`/`SATK`/`SHP`) are mutually exclusive with their corresponding non-seed values. If both are filled in, the JSON file **will not run**.

##### Character Stat Selection

Supports entering two modes in the `select_mode` key within the `SUPPORT` level:

| Property | Type | Description |
|------|------|------|
| `best` | `str` | See [`best Selection Mode`](#best-selection-mode) |
| `first` | `str` | See [`first Selection Mode`](#first-selection-mode) |

If the `select_mode` key is not filled, it defaults to `best`.

###### best Selection Mode

- Selects the maximum value of the first keyword in the `keywords` list.

###### first Selection Mode

- Prioritizes selecting the most frequent result from `keywords` that meet the conditions; if none meet them, selects the most frequent result from all `keywords`.

Partial source code is as follows (if you have better ideas or want to support more selection modes, feel free to open an issue):

```python
output = output_satisfied if output_satisfied else output_all

if mode == "first":
    most_common_data = output.get(keywords[0], None)
elif mode == "best":
    # Count which res_data appears the most in output
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

The `fight` object configures the action sequence during combat.

#### pos

The `pos` object defines the starting positions for the first 4 characters (LEADER, 2nd, 3rd, 4th).

**Coordinate System Description:**

- The cell where the **LEADER** is located is the origin `(0, 0)`.
- **x-axis**: Horizontal to the right is the positive direction.
- **y-axis**: Vertical downwards is the positive direction.
- Only considers points accessible by your own characters.

| Property | Type | Description |
|------|------|------|
| `"1"` | `[x, y]` | Position of the LEADER |
| `"2"` | `[x, y]` | Position of the 2nd member |
| `"3"` | `[x, y]` | Position of the 3rd member |
| `"4"` | `[x, y]` | Position of the 4th member |

**Situation 0 Example:**

![sample](./sample_pic/3x3SIT0.png)

```json
"pos": {
    "1": [0, 0],
    "2": [1, 0],
    "3": [0, 1],
    "4": [1, 1]
}
```

**Situation 1 Example:**

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

#### Action Object

SIT values like `"0"`, `"1"`, ... and each sub-object within `loop`, are all **action objects**.

Each action object **must only have** two properties:

| Property | Type | Description |
|------|------|------|
| `char` | `int` | Character number to operate, same as `1`~`4` in [`pos`](#pos) |
| `action` | `list[str]` | Action command sequence |

**`action` Command List:**

| Command | Direction |
|:----:|------|
| `U` | Up |
| `D` | Down |
| `L` | Left |
| `R` | Right |
| `S` | Stand STILL |

**Example:**

```json
"0": {
    "char": 4,
    "action": ["L", "D", "R", "R", "U", "U"]
}
```

---

#### loop

The `loop` object contains a set of action objects, numbered from `"0"`, to be **executed in a loop** until the level ends.

**Example:**

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

### Complete JSON Example

> The following example corresponds to `data/auto_combat/dungen_fight.json`

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

## Character and AR Name Retrieval

<!-- Expected to be deprecated after a major frontend update -->

Character names, IDs, and AR card names require looking up the index dictionaries under `MAH/docs`:

| File | Purpose |
|------|------|
| [`characters.json`](#characters) | High-star character index |
| [`characters_lowstar.json`](#characters_lowstar) | Low-star character index |
| [`ar.json`](#ar) | AR card index |

> ⚠️ **Do not manually modify the above index dictionary files!**

---

### characters

In `characters.json`, each character uses its **English name** as the key, and the value contains the card details:

| Field | Type | Description | Disallowed |
|------|------|------|--------|
| `rarity` | `int` | Star Rating | `1` ~ `5` |
| `element` | `str` | Element | `water` `fire` `wood` `world` `light` `dark` `god` `hero` `evil` `all` `zero` `infinity` |
| `weapon` | `str` | Weapon | `slash` `thrust` `knock` `snipe` `shoot` `none` `magic` `longslash` |
| `path` | `str` | Resource Path | — |

**Example:**

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

The structure of `characters_lowstar.json` is similar to `characters.json`, but low-star characters may have a **weapon of `varies`**, meaning that different elements correspond to different weapons:

**Example:**

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

> When `weapon` is `varies`, you must specify the `weapon` separately within the sub-objects for each element.

---

### AR

In `ar.json`, each AR card uses its **filename** as the key:

| Field | Type | Description |
|------|------|------|
| `jp_rawname` | `str` | Japanese Name of AR Card |
| `rarity` | `int` | Star Rating (`1` ~ `5`) |
| `tag` | `list[str]` | English names of characters appearing in the card |
| `path` | `str` | Resource Path |

**Example:**

```json
"ar_shino_moritaka.png": {
    "jp_rawname": "犬どもの戦場",
    "rarity": 4,
    "tag": ["shino", "moritaka"],
    "path": "ar\\ar_shino_moritaka.png"
}
```