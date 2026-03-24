# MAH

## Disclaimer

- This resource is OPEN SOURCE and FREE.
- This resource is provided "as is", without warranty of any kind, express or implied. Users must assume all risks associated with its use.
- The author shall not be liable for any direct, indirect, or consequential damages resulting from the use of this resource.
- This resource is an independent component; its MIT license is non-infectious and is not affected by the licenses of other software integrated with it.
- Any commercial activities based on this resource are completely unrelated to the original author, and users may not imply any official association or endorsement.

## Welcome to MAH, Here is the User Guide

1. This project **ONLY supports** Android emulators. The configuration requirements are as follows:
    - The screen ratio must be 16:9, and the recommended (and minimum) resolution is `1280x720`. Errors caused by not meeting the requirements will not be resolved.

2. The complete MAH software archive naming format is "MAH-Platform-Architecture-Version.zip"; everything else is a "spare part" that cannot be used separately. Please read carefully.
In most cases, you need to use the x64 architecture MAH, which means you need to download `MAH-win-x86_64-vXXX.zip` instead of `MAH-win-aarch64-vXXX.zip`.

## Features

### Launch Game

Launch the game and wait to enter the main menu.

### Dungeon Combat

Perform dungeon combat, including the following options:

- Level Selection: Supports all permanent dungeons. For event dungeons, it is supported and recommended to manually fill in partial keywords.

- Challenge Times: Specify challenge times. If it exceeds the current DP and you don't choose to use stamina items, it will run until DP is exhausted.

- Use Stamina Items: Automatically use stamina items.

- Team Selection: Fill in the corresponding team ID, which is the `team X` in the top left corner of each team slot.

- Import from `JSON` File: Supports reading content from standardized `JSON` files. See docs/`auto_combat_json_config.md` for detailed specifications.

  - Auto-fetch from `JSON`: Fetch all combat data from a single file.

  - Custom Combinations: Fetch combat data from different files.

#### Custom Support Character Selection

- Basic Info:

  1. Character Name (**Required**): Requires the internal English name of the character (most are identical to the official English name). A few special examples are listed below. For other details, please search the `JSON` dictionary index. The [`Search Method`](#search-methods-for-related-content) corresponds to the end of the document:
  
      - Smokygod: **the**smokygod
      - Hero: **the**hero
      - Protagonist: player

  2. Character ID (**Required**): Refers to which card of the given character it is.

  3. Artifact Level (**Optional**)

  4. AR Card (**Optional**): Requires the internal English name of the AR card (**Not the official name**). For details, search the `JSON` dictionary index. See [`Search Method`](#search-methods-for-related-content).

- Filter Support (**Optional**): If left blank, it automatically selects the one with the highest `absolute stats`:

  - Stat Filter: Filters based on stats actually shown to the player.

  - Seed Filter: Filters based on a character's seed stats.

- Auto Team Formation: Same as `Import from JSON File`.

- Battle List Selection: Same as `Import from JSON File`.

### Stamina Combat

Most properties are identical to Dungeon Combat. Here are the differences:

- Level Selection: Supports Chapter 14 Flower Nodes, 3 permanent daily quests. Event quests are supported, and it is `recommended` to manually fill in partial keywords.

  - Custom Daily Quests: Select by manually typing `related keywords` from the daily quests. Can be filled like the following example `Breakthrough Trials - Aether（3）`:

    1. Custom Level Name: Supported and `recommended` to fill in partial keywords (Level Name: `Aether`)

    2. Difficulty Keywords: Supported and `recommended` to fill in partial keywords (Level Difficulty: `（3）`)

- Use Stamina Potions: Order of use is `Full` -> `Half` -> `Mini`.

### Claim Rewards

Automatically claim weekly quests and items in the gift box.

## Search Methods for Related Content

**A handy search plugin is currently in active development.**

Character names, IDs, and AR card names require checking the index dictionaries under `MAH/docs`:

| File | Purpose |
|------|------|
| [`characters.json`](#characters) | High-star character index |
| [`characters_lowstar.json`](#characters_lowstar) | Low-star character index |
| [`ar.json`](#ar) | AR card index |

> ⚠️ **Do not manually modify the index dictionary files above!**

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

***If the support character is a low-star character, please do not enter an ID.***

The structure of `characters_lowstar.json` is similar to `characters.json`, but low-star characters (2 stars and below) may have a **weapon of `varies`**, meaning that different elements correspond to different weapons:

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
| `jp_rawname` | `str` | Japanese Name |
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
