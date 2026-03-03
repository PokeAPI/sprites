# Contributing Sprites

## Overview

This repository provides helper scripts and documentation to manually maintain the default sprite collection located in `sprites/pokemon/`. Our goal is to provide a complete set of "Gen 5 style" (Black & White) sprites for the entire National Dex.

This initial version of the maintenance workflow focuses specifically on:

1. **Auditing** the `sprites/pokemon/` folder for missing assets.
2. **Synchronizing** with Smogon community spreadsheets for Pokémon with **IDs 650+** (National Dex entries beyond the official Gen 5 games).

## Missing Sprites Tracking and Smogon Synchronization

### 1. Identifying Missing Sprites

**Script:** `scripts/check_missing_sprites.py`

This script identifies which Pokémon or forms are missing from the `sprites/pokemon/` directory.

* **Data Sources:** It references `pokemon.csv` and `pokemon_forms.csv` from the PokéAPI database.
* **Logic:** It checks for the existence of four primary assets for every entry:
  * Front (Default & Shiny)
  * Back (Default & Shiny)
* **Output:** Missing entries are logged in `missing_sprites.csv` to track our progress toward a 100% complete National Dex.

### 2. Synchronizing with Smogon

**Script:** `scripts/smogon_download.py`

Since official Gen 5 sprites do not exist for newer Pokémon, we source community-made assets from Smogon. This script automates the download and renaming process.

#### Filename Mapping

Smogon uses a shorthand naming system. The script (utilizing logic from `renameSmogon.sh`) translates these into the PokéAPI structure:

| Suffix | Sprite Type | Example |
| --- | --- | --- |
| *(None)* | Front Default | `100.png` |
| `s` | Front Shiny | `100s.png` |
| `b` | Back Default | `100b.png` |
| `sb` | Back Shiny | `100sb.png` |
| `g` | Gigantamax | `100g.png` |
| `_1` | Variant/Form | `100_1.png` |

### 3. Mandatory Manual Verification

The Smogon source data is community-maintained and contains known inconsistencies. **The scripts do not handle these automatically.** Contributors must manually review and correct the following:

### Known Data Quirks

* **Orientation Swaps:** Some filenames are reversed in the source.
  * *Example:* For **Blastoise**, `009_2.png` is often the **Back** sprite despite being labeled as a front variant.
  * **Action:** Verify the image visually and ensure it is placed in the correct directory.

* **Duplicate Variant IDs:** Different forms may share the same numerical suffix in Smogon spreadsheets.
  * *Example:* Both **Hoenn Cap** and **Partner Cap** Pikachu may use `_8`.
  * **Action:** Cross-reference with the spreadsheet context and manually rename files to match their unique PokéAPI form IDs.

* **Form Mapping:** Ensure variants (e.g., `_1`, `_2`) are correctly mapped using `forms.json`. If a new form is added, you must update `forms.json` manually.

### How to Use

1. **Check for gaps:** `python scripts/check_missing_sprites.py`
2. **Sync Smogon assets:** `python scripts/smogon_download.py`
3. **Manual Fixes:** Review the downloaded files against the "Known Issues" above and correct names/folders manually before submitting a PR.
