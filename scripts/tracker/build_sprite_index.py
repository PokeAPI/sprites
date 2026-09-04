"""Repository asset indexer for Sprite Finder.

Scans the local `sprites/` filesystem (pokemon, items, badges, types)
and builds a compact manifest `website/data/sprite_index.json` with zero
external API dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SPRITES_DIR = PROJECT_ROOT / "sprites"
WEBSITE_DATA_DIR = PROJECT_ROOT / "website" / "data"

GITHUB_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
POKEMON_CSV_URL = f"{GITHUB_BASE_URL}/pokemon.csv"
FORMS_CSV_URL = f"{GITHUB_BASE_URL}/pokemon_forms.csv"
SPECIES_CSV_URL = f"{GITHUB_BASE_URL}/pokemon_species.csv"

def load_pokeapi_game_metadata() -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Dynamically derives generation titles, game titles, and chronological order from PokéAPI CSVs."""
    gen_titles: dict[str, str] = {}
    game_titles: dict[str, str] = {}
    game_order: dict[str, list[str]] = {}

    try:
        df_gen = pd.read_csv(f"{GITHUB_BASE_URL}/generations.csv")
        df_gn = pd.read_csv(f"{GITHUB_BASE_URL}/generation_names.csv")
        df_gn_en = df_gn[df_gn["local_language_id"] == 9]
        gen_map = dict(zip(df_gn_en["generation_id"], df_gn_en["name"]))
        gen_titles = dict(zip(df_gen["identifier"], df_gen["id"].map(gen_map)))

        df_vg = pd.read_csv(f"{GITHUB_BASE_URL}/version_groups.csv")
        df_v = pd.read_csv(f"{GITHUB_BASE_URL}/versions.csv")
        df_vn = pd.read_csv(f"{GITHUB_BASE_URL}/version_names.csv")
        df_vn_en = df_vn[df_vn["local_language_id"] == 9]

        v_names = dict(zip(df_vn_en["version_id"], df_vn_en["name"]))
        # Individual version names (e.g. gold, silver, crystal)
        for _, row in df_v.iterrows():
            vid = row["id"]
            ident = str(row["identifier"])
            if vid in v_names:
                game_titles[ident] = v_names[vid]

        # Version groups (e.g. red-blue, ruby-sapphire, black-white)
        for vgid, group in df_v.groupby("version_group_id"):
            names = [v_names.get(vid, "") for vid in group["id"] if vid in v_names]
            vg_row = df_vg[df_vg["id"] == vgid]
            if not vg_row.empty:
                ident = vg_row["identifier"].values[0]
                title = " & ".join(names)
                if ident == "red-green-japan":
                    title = "Red & Green (Japan)"
                game_titles[ident] = title

        # Folder aliases and community models
        if "omega-ruby-alpha-sapphire" in game_titles:
            game_titles["omegaruby-alphasapphire"] = game_titles["omega-ruby-alpha-sapphire"]
        if "champions" not in game_titles:
            game_titles["champions"] = "Champions (Community Models)"
        else:
            game_titles["champions"] = "Champions (Community Models)"

        # Chronological game order per generation from version_groups.csv
        gen_id_to_ident = dict(zip(df_gen["id"], df_gen["identifier"]))
        df_vg_sorted = df_vg.sort_values("order")
        for _, row in df_vg_sorted.iterrows():
            gid = row["generation_id"]
            gident = gen_id_to_ident.get(gid)
            if not gident:
                continue
            vident = row["identifier"]
            if gident not in game_order:
                game_order[gident] = []
            if vident == "gold-silver":
                game_order[gident].extend(["gold", "silver"])
            elif vident == "omega-ruby-alpha-sapphire":
                game_order[gident].extend(["omega-ruby-alpha-sapphire", "omegaruby-alphasapphire"])
            else:
                game_order[gident].append(vident)
    except Exception as e:
        print(f"[WARN] Failed to fetch dynamic game metadata from PokéAPI ({e}), using fallback formatting.")

    return gen_titles, game_titles, game_order

OTHER_TITLES: dict[str, str] = {
    "official-artwork": "Official Artwork (High-Res)",
    "home": "Pokémon HOME 3D Renders",
    "showdown": "Pokémon Showdown Battle GIFs",
    "dream-world": "Dream World Vector Art",
}

SUBPATH_ORDER: list[str] = [
    "",
    "transparent",
    "gbc",
    "gray",
    "transparent/gray",
    "shiny",
    "female",
    "shiny/female",
    "transparent/shiny",
    "back",
    "transparent/back",
    "back/gbc",
    "back/gray",
    "transparent/back/gray",
    "back/shiny",
    "back/female",
    "back/shiny/female",
    "transparent/back/shiny",
    "animated",
    "animated/shiny",
    "animated/female",
    "animated/shiny/female",
    "animated/back",
    "animated/back/shiny",
    "animated/back/female",
    "animated/back/shiny/female",
]

SUBCATEGORY_ORDER: list[str] = [
    "Default",
    "Transparent",
    "GBC Color",
    "Gray",
    "Transparent Gray",
    "Animated",
    "Icons",
]


def parse_gen_num(gen_str: str) -> int:
    """Extracts numeric generation (e.g. 'generation-iii' -> 3)."""
    roman_map = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9}
    match = re.search(r"generation-([a-z]+)", gen_str.lower())
    if match:
        return roman_map.get(match.group(1), 0)
    return 0


def get_symmetric_subpaths_for_subcat(subcat: str, gen_num: int, has_female: bool = False) -> list[str]:
    """Generates the canonical battle perspective matrix dynamically for any subcategory."""
    subcat_map = {
        "Transparent": ("transparent", "transparent/back"),
        "Animated": ("animated", "animated/back"),
        "GBC Color": ("gbc", "back/gbc"),
        "Gray": ("gray", "back/gray"),
        "Transparent Gray": ("transparent/gray", "transparent/back/gray"),
        "Default": ("", "back"),
    }
    pair = subcat_map.get(subcat)
    if not pair:
        return []
    front_base, back_base = pair

    def combine(base: str, variant: str) -> str:
        if not base:
            return variant
        if not variant:
            return base
        return f"{base}/{variant}"

    results = []
    # Front perspectives
    results.append(combine(front_base, ""))
    if gen_num >= 2:
        results.append(combine(front_base, "shiny"))
    if has_female and gen_num >= 4:
        results.append(combine(front_base, "female"))
        if gen_num >= 2:
            results.append(combine(front_base, "shiny/female"))

    # Back perspectives (battle sprites)
    results.append(combine(back_base, ""))
    if gen_num >= 2:
        results.append(combine(back_base, "shiny"))
    if has_female and gen_num >= 4:
        results.append(combine(back_base, "female"))
        if gen_num >= 2:
            results.append(combine(back_base, "shiny/female"))

    return results


def get_subcategory(subpath: str) -> str:
    """Categorizes variant subpaths into logical groups (Default, Transparent, Gray, etc.)."""
    if not subpath:
        return "Default"
    parts = set(subpath.split("/"))
    if "animated" in parts:
        return "Animated"
    if "transparent" in parts and "gray" in parts:
        return "Transparent Gray"
    if "transparent" in parts:
        return "Transparent"
    if "gray" in parts:
        return "Gray"
    if "gbc" in parts:
        return "GBC Color"
    return "Default"


def format_subpath_label(subpath: str, is_icon: bool = False) -> str:
    """Generates human-readable labels for any variation folder subpath."""
    if is_icon:
        if subpath == "":
            return "Menu Icon"
        if subpath == "female":
            return "Menu Icon (Female)"
        if subpath == "animated":
            return "Animated Menu Icon"
        return subpath.replace("/", " ").title()

    if subpath == "":
        return "Front Default"

    parts = set(subpath.split("/"))
    prefix = ""
    if "animated" in parts:
        prefix += "Front Animated " if "back" not in parts else "Back Animated "
    elif "transparent" in parts:
        prefix += "Front Transparent " if "back" not in parts else "Back Transparent "
    elif "gbc" in parts:
        prefix += "Front GBC Color " if "back" not in parts else "Back GBC Color "
    elif "gray" in parts:
        prefix += "Front Gray " if "back" not in parts else "Back Gray "
    elif "back" in parts:
        prefix += "Back "
    else:
        prefix += "Front "

    middle = ""
    if "gray" in parts and "transparent" in parts:
        middle += "Gray "
    if "shiny" in parts:
        middle += "Shiny "
    if "female" in parts:
        middle += "Female "

    label = (prefix + middle).strip()
    if label in ("Front", "Back"):
        label += " Default"
    return label


def build_index(output_file: Path | None = None) -> Path:
    start_time = time.time()
    dest = output_file or (WEBSITE_DATA_DIR / "sprite_index.json")
    dest.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INDEX] Scanning repository assets in: {SPRITES_DIR}")

    # 1. Fetch PokéAPI metadata
    print("[INDEX] Fetching PokéAPI metadata CSVs...")
    df_pk = pd.read_csv(POKEMON_CSV_URL)
    df_forms = pd.read_csv(FORMS_CSV_URL)
    df_species = pd.read_csv(SPECIES_CSV_URL)

    gen_titles, game_titles, game_order = load_pokeapi_game_metadata()

    species_gender_diff = dict(zip(df_species["id"], df_species["has_gender_differences"]))

    pokemon_list: list[dict[str, Any]] = []
    for _, row in df_pk.iterrows():
        sp_id = int(row["species_id"])
        pokemon_list.append({
            "id": int(row["id"]),
            "name": str(row["identifier"]),
            "species_id": sp_id,
            "has_gender_diff": bool(species_gender_diff.get(sp_id, 0)),
            "is_form": False,
        })

    for _, row in df_forms.iterrows():
        pokemon_list.append({
            "id": int(row["id"]),
            "name": str(row["identifier"]),
            "pokemon_id": int(row["pokemon_id"]),
            "is_form": True,
        })

    # 2. Filesystem Scan of sprites/pokemon
    base_pk = SPRITES_DIR / "pokemon"
    folder_files: dict[str, list[int | str]] = {}
    folder_exts: dict[str, str] = {}

    if base_pk.exists():
        for p in base_pk.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".png", ".gif", ".svg", ".jpg"):
                rel_folder = p.parent.relative_to(PROJECT_ROOT).as_posix()
                ext = p.suffix.lower()
                if rel_folder not in folder_files:
                    folder_files[rel_folder] = []
                    folder_exts[rel_folder] = ext
                folder_files[rel_folder].append(int(p.stem) if p.stem.isdigit() else p.stem)

    for f in folder_files:
        folder_files[f].sort(key=lambda x: (isinstance(x, str), x))

    # 3. Dynamic Root Views (Scan sprites/pokemon excluding other and versions)
    root_subdirs = [""]
    for d in base_pk.iterdir():
        if d.is_dir() and d.name not in ("other", "versions"):
            for sub in [d] + [c for c in d.rglob("*") if c.is_dir()]:
                rel = sub.relative_to(base_pk).as_posix()
                root_subdirs.append(rel)

    root_views: list[dict[str, Any]] = []
    for sub in sorted(root_subdirs, key=lambda s: (SUBPATH_ORDER.index(s) if s in SUBPATH_ORDER else 999, s)):
        folder_rel = f"sprites/pokemon/{sub}".rstrip("/")
        if folder_rel in folder_files and len(folder_files[folder_rel]) > 0:
            root_views.append({
                "label": format_subpath_label(sub),
                "folder": folder_rel,
                "ext": folder_exts.get(folder_rel, ".png"),
                "female": "female" in sub.split("/"),
            })

    # 4. Dynamic Other Sprite Collections (Scan sprites/pokemon/other/*)
    other_base = base_pk / "other"
    other_categories: list[dict[str, Any]] = []
    if other_base.exists():
        for cat_dir in sorted(other_base.iterdir()):
            if not cat_dir.is_dir():
                continue
            badge = cat_dir.name
            cat_name = OTHER_TITLES.get(badge, badge.replace("-", " ").title())
            views = []

            # Check root of category
            cat_rel = cat_dir.relative_to(PROJECT_ROOT).as_posix()
            if cat_rel in folder_files and len(folder_files[cat_rel]) > 0:
                views.append({
                    "label": "Front Default",
                    "folder": cat_rel,
                    "ext": folder_exts.get(cat_rel, ".png"),
                    "female": False,
                    "subpath": "",
                })

            # Check subdirectories
            for d in sorted(cat_dir.rglob("*")):
                if not d.is_dir():
                    continue
                f_rel = d.relative_to(PROJECT_ROOT).as_posix()
                subpath = d.relative_to(cat_dir).as_posix()
                if f_rel in folder_files and len(folder_files[f_rel]) > 0:
                    views.append({
                        "label": format_subpath_label(subpath),
                        "folder": f_rel,
                        "ext": folder_exts.get(f_rel, ".png"),
                        "female": "female" in subpath.split("/"),
                        "subpath": subpath,
                    })

            views.sort(key=lambda v: (SUBPATH_ORDER.index(v["subpath"]) if v["subpath"] in SUBPATH_ORDER else 999, v["subpath"]))
            for v in views:
                v.pop("subpath", None)

            ext = views[0]["ext"] if views else ".png"
            is_large = ext == ".svg" or badge in ("official-artwork", "home", "dream-world")

            if views:
                other_categories.append({
                    "name": cat_name,
                    "badge": badge,
                    "is_large": is_large,
                    "views": views,
                })

    # 5. Dynamically Discover Versions Structure
    versions_base = SPRITES_DIR / "pokemon" / "versions"
    generations_data: list[dict[str, Any]] = []

    if versions_base.exists():
        gen_order = list(gen_titles.keys())
        for gen_dir in sorted(
            [d for d in versions_base.iterdir() if d.is_dir()],
            key=lambda d: (gen_order.index(d.name) if d.name in gen_order else 999, d.name),
        ):
            gen_id = gen_dir.name
            gen_title = gen_titles.get(gen_id, gen_id.replace("-", " ").title())
            gen_num = parse_gen_num(gen_id)

            games_dict: dict[str, list[dict[str, Any]]] = {}
            icons_list: list[dict[str, Any]] = []

            for f in gen_dir.rglob("*"):
                if not f.is_dir():
                    continue
                rel = f.relative_to(gen_dir).as_posix()
                parts = rel.split("/")
                primary = parts[0]
                subpath = "/".join(parts[1:])
                folder_rel = f.relative_to(PROJECT_ROOT).as_posix()

                if folder_rel not in folder_files or len(folder_files[folder_rel]) == 0:
                    continue

                ext = folder_exts.get(folder_rel, ".png")

                if primary == "icons":
                    icons_list.append({
                        "label": format_subpath_label(subpath, is_icon=True),
                        "folder": folder_rel,
                        "ext": ext,
                        "subpath": subpath,
                    })
                else:
                    if primary not in games_dict:
                        games_dict[primary] = []
                    is_icon = subpath == "icons" or subpath.startswith("icons/")
                    games_dict[primary].append({
                        "label": format_subpath_label(subpath, is_icon=is_icon),
                        "folder": folder_rel,
                        "ext": ext,
                        "subpath": subpath,
                        "subcategory": get_subcategory(subpath),
                        "female": "female" in subpath.split("/"),
                    })

            # Check direct children for files
            for child in gen_dir.iterdir():
                if child.is_dir():
                    primary = child.name
                    folder_rel = child.relative_to(PROJECT_ROOT).as_posix()
                    if folder_rel in folder_files and len(folder_files[folder_rel]) > 0:
                        ext = folder_exts.get(folder_rel, ".png")
                        if primary == "icons":
                            if not any(i["folder"] == folder_rel for i in icons_list):
                                icons_list.insert(0, {
                                    "label": "Menu Icon",
                                    "folder": folder_rel,
                                    "ext": ext,
                                    "subpath": "",
                                    "subcategory": "Icons",
                                    "female": False,
                                })
                        else:
                            if primary not in games_dict:
                                games_dict[primary] = []
                            if not any(v["folder"] == folder_rel for v in games_dict[primary]):
                                games_dict[primary].insert(0, {
                                    "label": "Front Default",
                                    "folder": folder_rel,
                                    "ext": ext,
                                    "subpath": "",
                                    "subcategory": "Default",
                                    "female": False,
                                })

            order_list = game_order.get(gen_id, [])
            sorted_game_keys = sorted(
                games_dict.keys(),
                key=lambda k: (order_list.index(k) if k in order_list else 999, k),
            )

            games_data: list[dict[str, Any]] = []
            for game_key in sorted_game_keys:
                views = games_dict[game_key]

                # Ensure symmetric perspective matrices for present subcategories
                present_subcats = {v["subcategory"] for v in views if v["subcategory"] != "Icons"}
                has_female = gen_num >= 4 and any(v.get("female") for v in views)
                for subcat in present_subcats:
                    expected_subpaths = get_symmetric_subpaths_for_subcat(subcat, gen_num, has_female=has_female)
                    if expected_subpaths:
                        existing_subpaths = {v["subpath"] for v in views if v["subcategory"] == subcat}
                        for subp in expected_subpaths:
                            if subp not in existing_subpaths:
                                ext = ".gif" if "animated" in subp.split("/") else ".png"
                                rel_folder = f"sprites/pokemon/versions/{gen_id}/{game_key}/{subp}".rstrip("/")
                                views.append({
                                    "label": format_subpath_label(subp, is_icon=False),
                                    "folder": rel_folder,
                                    "ext": ext,
                                    "subpath": subp,
                                    "subcategory": subcat,
                                    "female": "female" in subp.split("/"),
                                })

                views.sort(key=lambda v: (
                    SUBCATEGORY_ORDER.index(v["subcategory"]) if v.get("subcategory") in SUBCATEGORY_ORDER else 999,
                    SUBPATH_ORDER.index(v["subpath"]) if v["subpath"] in SUBPATH_ORDER else 999,
                    v["subpath"],
                ))
                game_name = game_titles.get(game_key, game_key.replace("-", " ").title())
                games_data.append({
                    "name": game_name,
                    "folder": f"sprites/pokemon/versions/{gen_id}/{game_key}",
                    "views": views,
                })

            icons_list.sort(key=lambda x: x["subpath"])

            if games_data or icons_list:
                generations_data.append({
                    "id": gen_id,
                    "title": gen_title,
                    "games": games_data,
                    "icons": icons_list,
                })

    # 6. Badges
    base_badges = SPRITES_DIR / "badges"
    badges_list: list[int] = []
    if base_badges.exists():
        badges_list = sorted([int(p.stem) for p in base_badges.glob("*.png") if p.stem.isdigit()])

    # 7. Items
    base_items = SPRITES_DIR / "items"
    items_dict: dict[str, list[str]] = {}
    if base_items.exists():
        for p in base_items.rglob("*.png"):
            rel = p.relative_to(base_items).as_posix()
            items_dict.setdefault(p.stem, []).append(rel)

    # 8. Types
    base_types = SPRITES_DIR / "types"
    types_dict: dict[str, dict[str, list[str]]] = {}
    if base_types.exists():
        for p in base_types.rglob("*.png"):
            rel = p.relative_to(base_types).as_posix()
            parts = rel.split("/")
            if len(parts) >= 3:
                types_dict.setdefault(parts[0], {}).setdefault(parts[1], []).append("/".join(parts[2:]))

    manifest = {
        "version": "2.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {
            "pokemon_entities": len(pokemon_list),
            "pokemon_folders": len(folder_files),
            "generations": len(generations_data),
            "badges": len(badges_list),
            "items": len(items_dict),
            "type_generations": len(types_dict),
        },
        "pokemon_list": pokemon_list,
        "root_views": root_views,
        "other_categories": other_categories,
        "generations": generations_data,
        "folder_files": folder_files,
        "badges_list": badges_list,
        "items_dict": items_dict,
        "types_dict": types_dict,
    }

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"))

    size_kb = dest.stat().st_size / 1024
    elapsed = time.time() - start_time
    print(f"[SUCCESS] Pre-categorized sprite manifest written to: {dest} ({size_kb:.1f} KB in {elapsed:.2f}s)")
    return dest



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build offline sprite index for Sprite Finder")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Destination JSON path")
    args = parser.parse_args()
    build_index(args.output)
