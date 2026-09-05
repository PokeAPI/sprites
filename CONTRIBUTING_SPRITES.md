# Contributing Sprites

## Overview

This repository provides helper scripts and documentation to manually maintain the default sprite collection located in `sprites/pokemon/`. Our goal is to provide a complete set of "Gen 5 style" (Black & White) sprites for the entire National Dex.

This initial version of the maintenance workflow focuses specifically on:

1. **Auditing** the `sprites/pokemon/` folder for missing assets.
2. **Synchronizing** with Smogon community spreadsheets for Pokémon with **IDs 650+** (National Dex entries beyond the official Gen 5 games).

## Missing Sprites Tracking and Smogon Synchronization

### 1. Identifying Missing Sprites

**Script:** `scripts/tracker/sprite_audit.py`

This script identifies missing, corrupt, or incorrectly sized sprites across multiple asset categories and cosmetic forms.

* **Data Sources:** References `pokemon.csv`, `pokemon_forms.csv`, and `version_groups.csv` from the PokéAPI database.
* **Supported Categories (`--category`):**
  * `default`: Front & Back (Default & Shiny) Gen 5 pixel art (`96x96`).
  * `official-artwork`: High-res official artwork renders (`475x475`).
  * `home`: Pokémon HOME 3D renders (`512x512`).
  * `showdown`: Pokémon Showdown animated battle sprites (`.gif`).
  * `dream-world`: Dream World vector sprites (`.svg`/`.png`).
  * `all`: Runs audits across all asset categories.
* **Cosmetic Form Auditing (`--include-forms`):** Audits non-default cosmetic forms (such as Sinistea Antique, Polteageist Antique, Vivillon patterns, Unown letters, Alcremie forms) defined in `pokemon_forms.csv`.
* **Output & Reports:**
  * Interactive HTML dashboard generated directly to `website/audit.html` (viewable on GitHub Pages). Custom path configurable via `-o` / `--output`.
  * Grouped issues logged to CSV (`scripts/tracker/sprite_audit_report.csv`).
  * Optional `--build-index` flag generates the offline repository manifest (`website/data/sprite_index.json`) for Sprite Finder.

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

1. **Audit default sprites:**
   ```bash
   python scripts/tracker/sprite_audit.py --category default
   ```
2. **Audit all categories including cosmetic forms (updates GitHub Pages dashboard):**
   ```bash
   python scripts/tracker/sprite_audit.py --category all --include-forms
   ```
3. **Audit a specific category (e.g. Showdown or Official Artwork):**
   ```bash
   python scripts/tracker/sprite_audit.py --category showdown
   python scripts/tracker/sprite_audit.py --category official-artwork
   ```
4. **Sync Smogon assets:**
   ```bash
   python scripts/smogon_download.py
   ```
5. **Manual Fixes:** Review the downloaded files against the "Known Issues" above and correct names/folders manually before submitting a PR.
