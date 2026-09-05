"""Repository asset indexer for Sprite Finder.

Scans the local `sprites/` filesystem (pokemon, items, badges, types)
and builds a compact manifest `website/data/sprite_index.json` with zero
external API dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import (
    GITHUB_BASE_URL,
    PROJECT_ROOT,
    SPRITES_DIR,
    UNIFIED_VERSION_GROUPS,
    WEBSITE_DIR,
    get_candidate_stems,
    load_csv,
    reconfigure_utf8,
    roman_to_int,
)

reconfigure_utf8()

WEBSITE_DATA_DIR = WEBSITE_DIR / "data"

def load_pokeapi_game_metadata() -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, list[str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Dynamically derives generation titles, game titles, and chronological order from PokéAPI CSVs."""
    gen_titles: dict[str, str] = {}
    game_titles: dict[str, str] = {}
    game_order: dict[str, list[str]] = {}

    gen_rows = load_csv(f"{GITHUB_BASE_URL}/generations.csv")
    gn_rows = load_csv(f"{GITHUB_BASE_URL}/generation_names.csv")
    vg_rows = load_csv(f"{GITHUB_BASE_URL}/version_groups.csv")
    v_rows = load_csv(f"{GITHUB_BASE_URL}/versions.csv")
    vn_rows = load_csv(f"{GITHUB_BASE_URL}/version_names.csv")

    try:
        gen_map = {r["generation_id"]: r["name"] for r in gn_rows if r.get("local_language_id") == "9"}
        gen_titles = {r["identifier"]: gen_map.get(r["id"], r["identifier"].replace("-", " ").title()) for r in gen_rows}

        v_names = {r["version_id"]: r["name"] for r in vn_rows if r.get("local_language_id") == "9"}
        for r in v_rows:
            vid = r["id"]
            ident = r["identifier"]
            if vid in v_names:
                game_titles[ident] = v_names[vid]

        # Version groups (e.g. red-blue, ruby-sapphire, black-white)
        vg_to_versions: dict[str, list[dict[str, str]]] = defaultdict(list)
        for r in v_rows:
            vg_to_versions[r["version_group_id"]].append(r)

        vg_by_id = {r["id"]: r for r in vg_rows}
        for vgid, group in vg_to_versions.items():
            names = [v_names.get(r["id"], "") for r in group if r["id"] in v_names]
            vg_row = vg_by_id.get(vgid)
            if vg_row:
                ident = vg_row["identifier"]
                title = " & ".join(names)
                if ident == "red-green-japan":
                    title = "Red & Green (Japan)"
                title = title.replace("\ufffd", "'").replace("’", "'").replace("‘", "'")
                game_titles[ident] = title

        for k, v in list(game_titles.items()):
            game_titles[k] = v.replace("\ufffd", "'").replace("’", "'").replace("‘", "'")

        # Folder aliases, unified collections, and community models
        if "omega-ruby-alpha-sapphire" in game_titles:
            game_titles["omegaruby-alphasapphire"] = game_titles["omega-ruby-alpha-sapphire"]
        game_titles["champions"] = "Champions (Community Models)"
        game_titles["black-white"] = "Black & White / Black 2 & White 2"
        game_titles["ultra-sun-ultra-moon"] = "Sun & Moon / Ultra Sun & Ultra Moon"

        # Chronological game order per generation from version_groups.csv
        gen_id_to_ident = {r["id"]: r["identifier"] for r in gen_rows}
        vg_sorted = sorted(vg_rows, key=lambda r: int(r.get("order", 0)))
        for row in vg_sorted:
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

    return gen_titles, game_titles, game_order, gen_rows, vg_rows, v_rows


def build_canonical_games(
    vg_rows: list[dict[str, str]],
    v_rows: list[dict[str, str]],
    gen_rows: list[dict[str, str]],
    versions_base: Path,
) -> dict[str, list[str]]:
    """Dynamically builds the canonical games matrix per generation from PokéAPI version groups and local directories."""
    if not gen_rows or not vg_rows:
        return {}

    gen_map = {r["id"]: r["identifier"] for r in gen_rows}
    canonical_games: dict[str, list[str]] = {}

    gen_to_vg: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in sorted(vg_rows, key=lambda x: int(x.get("order", 0))):
        gen_to_vg[r["generation_id"]].append(r)

    for gid, group in gen_to_vg.items():
        gident = gen_map.get(gid)
        if not gident:
            continue
        gen_dir = versions_base / gident
        disk_folders = [d.name for d in gen_dir.iterdir() if d.is_dir() and d.name != "icons"] if gen_dir.exists() else []

        canonical_for_gen: list[str] = []
        for row in group:
            vg_id = row["id"]
            vg_ident = str(row["identifier"])

            # Map unified sibling version groups to their upstream parent directory
            actual_ident = UNIFIED_VERSION_GROUPS.get(vg_ident, vg_ident)

            # 1. Direct directory match
            if actual_ident in disk_folders:
                if actual_ident not in canonical_for_gen:
                    canonical_for_gen.append(actual_ident)
                continue

            # 2. Normalized unhyphenated match (e.g. omega-ruby-alpha-sapphire -> omegaruby-alphasapphire)
            unhyphen = actual_ident.replace("-", "")
            match_unhyphen = [f for f in disk_folders if f.replace("-", "") == unhyphen]
            if match_unhyphen:
                for f in match_unhyphen:
                    if f not in canonical_for_gen:
                        canonical_for_gen.append(f)
                continue

            # 3. Individual versions match (e.g. gold-silver -> gold, silver)
            if v_rows:
                vg_versions = [r["identifier"] for r in v_rows if r.get("version_group_id") == vg_id]
                matching_v = [v for v in vg_versions if v in disk_folders]
                if matching_v:
                    for v in matching_v:
                        if v not in canonical_for_gen:
                            canonical_for_gen.append(v)
                    continue

            # 4. Standalone games not yet populated on disk (exclude expansions and unified siblings)
            if (
                vg_ident not in UNIFIED_VERSION_GROUPS
                and not vg_ident.startswith("the-")
                and vg_ident not in ("colosseum", "xd", "blue-japan", "mega-dimension")
            ):
                if vg_ident not in canonical_for_gen:
                    canonical_for_gen.append(vg_ident)

        canonical_games[gident] = canonical_for_gen

    return canonical_games

OTHER_TITLES: dict[str, str] = {
    "official-artwork": "Official Artwork (High-Res)",
    "home": "Pokémon HOME 3D Renders",
    "showdown": "Pokémon Showdown Battle GIFs",
    "dream-world": "Dream World Vector Art",
}

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
    """Extracts numeric generation (e.g. 'generation-iii' -> 3, 'generation-x' -> 10)."""
    match = re.search(r"generation-([a-z]+)", gen_str.lower())
    if match:
        return roman_to_int(match.group(1))
    return 0


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


def subpath_sort_key(subpath: str) -> tuple[int, int, int, int, str]:
    """Algorithmic sorting key for perspective subpaths."""
    if not subpath:
        return (0, 0, 0, 0, "")
    parts = set(subpath.split("/"))
    subcat = get_subcategory(subpath)
    subcat_rank = SUBCATEGORY_ORDER.index(subcat) if subcat in SUBCATEGORY_ORDER else 99
    is_back = 1 if "back" in parts else 0
    is_female = 1 if "female" in parts else 0
    is_shiny = 1 if "shiny" in parts else 0
    return (subcat_rank, is_back, is_female, is_shiny, subpath)


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

    # In Gen 2 (Crystal) and Gen 4 (Diamond/Pearl, Platinum, HeartGold/SoulSilver), animated sprites only existed for the front battle entrance; back sprites were purely static in-game
    if subcat == "Animated" and (gen_num == 2 or gen_num == 4):
        return results

    # Back perspectives (battle sprites)
    results.append(combine(back_base, ""))
    if gen_num >= 2:
        results.append(combine(back_base, "shiny"))
    if has_female and gen_num >= 4:
        results.append(combine(back_base, "female"))
        if gen_num >= 2:
            results.append(combine(back_base, "shiny/female"))

    return results


def format_subpath_label(subpath: str, is_icon: bool = False) -> str:
    """Generates human-readable labels for any variation folder subpath."""
    if is_icon:
        return {"": "Menu Icon", "female": "Menu Icon (Female)", "animated": "Animated Menu Icon"}.get(
            subpath, subpath.replace("/", " ").title()
        )
    if not subpath:
        return "Front Default"

    parts = set(subpath.split("/"))
    direction = "Back" if "back" in parts else "Front"
    mods = []
    for tag, name in (("animated", "Animated"), ("transparent", "Transparent"), ("gbc", "GBC Color"), ("gray", "Gray")):
        if tag in parts:
            mods.append(name)
            break
    if "transparent" in parts and "gray" in parts and "Gray" not in mods:
        mods.append("Gray")
    if "shiny" in parts:
        mods.append("Shiny")
    if "female" in parts:
        mods.append("Female")

    label = f"{direction} {' '.join(mods)}".strip()
    return f"{label} Default" if label in ("Front", "Back") else label


def build_index(output_file: Path | None = None) -> Path:
    start_time = time.time()
    dest = output_file or (WEBSITE_DATA_DIR / "sprite_index.json")
    dest.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INDEX] Scanning repository assets in: {SPRITES_DIR}")

    # 1. Fetch PokéAPI metadata
    print("[INDEX] Fetching PokéAPI metadata CSVs...")
    df_pk = load_csv(f"{GITHUB_BASE_URL}/pokemon.csv")
    df_forms = load_csv(f"{GITHUB_BASE_URL}/pokemon_forms.csv")
    df_species = load_csv(f"{GITHUB_BASE_URL}/pokemon_species.csv")

    gen_titles, game_titles, game_order, gen_rows, vg_rows, v_rows = load_pokeapi_game_metadata()

    # Load types metadata
    types_list: list[dict[str, Any]] = []
    try:
        types_rows = load_csv(f"{GITHUB_BASE_URL}/types.csv")
        for r in types_rows:
            types_list.append({
                "id": int(r["id"]),
                "name": str(r["identifier"]),
            })
    except Exception as e:
        print(f"[WARN] Failed to load types CSV ({e})")

    # Build game_indices mapping: game_id -> list of pokemon IDs
    game_indices: dict[str, list[int]] = {}
    try:
        gi_rows = load_csv(f"{GITHUB_BASE_URL}/pokemon_game_indices.csv")
        v_to_vg = {r["id"]: r["version_group_id"] for r in v_rows}
        vg_ident_map = {r["id"]: r["identifier"] for r in vg_rows}
        game_poke_sets: dict[str, set[int]] = defaultdict(set)

        for r in gi_rows:
            vid = r.get("version_id")
            pid = r.get("pokemon_id")
            if vid and pid:
                vg_id = v_to_vg.get(vid)
                if vg_id:
                    vg_key = vg_ident_map.get(vg_id)
                    if vg_key:
                        game_poke_sets[vg_key].add(int(pid))

        if "black-2-white-2" in game_poke_sets:
            game_poke_sets.setdefault("black-white", set()).update(game_poke_sets["black-2-white-2"])
        if "sun-moon" in game_poke_sets:
            game_poke_sets.setdefault("ultra-sun-ultra-moon", set()).update(game_poke_sets["sun-moon"])

        game_indices = {k: sorted(list(v)) for k, v in game_poke_sets.items()}
    except Exception as e:
        print(f"[WARN] Failed to load game indices ({e})")

    vg_gen_map = {r["id"]: int(r["generation_id"]) for r in vg_rows if r.get("generation_id")}
    species_gender_diff = {r["id"]: (r.get("has_gender_differences") == "1") for r in df_species}
    species_generation = {r["id"]: int(r["generation_id"]) for r in df_species if r.get("generation_id")}
    pk_species_map = {r["id"]: r["species_id"] for r in df_pk}

    forms_by_pk: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in df_forms:
        forms_by_pk[r["pokemon_id"]].append(r)

    # Determine true debut generation for varieties and forms
    pk_debut_gen: dict[int, int] = {}
    for r in df_pk:
        p_id = int(r["id"])
        s_id = r["species_id"]
        is_def = r.get("is_default", "1")
        if is_def == "1":
            pk_debut_gen[p_id] = species_generation.get(s_id, 1)
        else:
            matching_forms = forms_by_pk.get(str(p_id), [])
            if matching_forms:
                form_gens = [vg_gen_map[f["introduced_in_version_group_id"]] for f in matching_forms if f.get("introduced_in_version_group_id") in vg_gen_map]
                pk_debut_gen[p_id] = min(form_gens) if form_gens else species_generation.get(s_id, 1)
            else:
                pk_debut_gen[p_id] = species_generation.get(s_id, 1)

    def is_dimorphic_entity(pk_id: int, identifier: str, sp_id: int | str) -> bool:
        if not species_gender_diff.get(str(sp_id), False):
            return False
        name = identifier.lower()
        if "-mega" in name:
            return False
        matching_forms = forms_by_pk.get(str(pk_id), [])
        if any(f.get("is_mega") == "1" for f in matching_forms):
            return False
        if "-gmax" in name:
            return False
        if name.endswith("-female"):
            return False
        if name in ("basculegion-male", "oinkologne-male"):
            return False
        if name.startswith("pikachu-") or name == "eevee-starter":
            return False
        if any(reg in name for reg in ("-alola", "-galar", "-paldea")):
            return False
        if "-hisui" in name and name != "sneasel-hisui":
            return False
        if "-totem" in name:
            return False
        return True

    pokemon_list: list[dict[str, Any]] = []
    for r in df_pk:
        pk_id = int(r["id"])
        sp_id = int(r["species_id"])
        gen_id = pk_debut_gen.get(pk_id, species_generation.get(str(sp_id), 1))
        pokemon_list.append({
            "id": pk_id,
            "name": str(r["identifier"]),
            "species_id": sp_id,
            "has_gender_diff": is_dimorphic_entity(pk_id, str(r["identifier"]), sp_id),
            "generation_id": int(gen_id),
            "is_form": False,
            "file_stem": str(pk_id),
            "candidate_stems": [str(pk_id)],
        })

    # Only include non-default cosmetic forms (is_default == 0) to avoid duplicating regular Pokémon
    for r in df_forms:
        if r.get("is_default") == "0":
            f_id = int(r["id"])
            pk_id = int(r["pokemon_id"])
            sp_id = int(pk_species_map.get(str(pk_id), pk_id))
            form_ident = str(r.get("form_identifier") or "")
            vg_id = r.get("introduced_in_version_group_id")
            if vg_id and vg_id in vg_gen_map:
                gen_id = vg_gen_map[vg_id]
            else:
                gen_id = pk_debut_gen.get(pk_id, species_generation.get(str(sp_id), 1))

            candidate_stems = get_candidate_stems(pk_id, f_id, r.get("identifier", ""), is_form=True, form_identifier=form_ident)

            pokemon_list.append({
                "id": f_id,
                "name": str(r["identifier"]),
                "pokemon_id": pk_id,
                "form_id": f_id,
                "form_identifier": form_ident,
                "species_id": sp_id,
                "has_gender_diff": False,
                "generation_id": int(gen_id),
                "is_form": True,
                "file_stem": candidate_stems[0],
                "candidate_stems": candidate_stems,
            })

    # 2. Filesystem Scan of sprites/pokemon
    base_pk = SPRITES_DIR / "pokemon"
    folder_files: dict[str, list[int | str]] = defaultdict(list)
    folder_exts: dict[str, str] = {}

    if base_pk.exists():
        for p in base_pk.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".png", ".gif", ".svg", ".jpg"):
                rel_folder = p.parent.relative_to(PROJECT_ROOT).as_posix()
                folder_files[rel_folder].append(int(p.stem) if p.stem.isdigit() else p.stem)
                folder_exts.setdefault(rel_folder, p.suffix.lower())

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
    for sub in sorted(root_subdirs, key=subpath_sort_key):
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

            views.sort(key=lambda v: subpath_sort_key(v["subpath"]))
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
    canonical_games_dict = build_canonical_games(vg_rows, v_rows, gen_rows, versions_base)
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

            # Ensure canonical core games are tracked even if not yet populated on disk
            canonical_games = canonical_games_dict.get(gen_id, [])
            for cg_key in canonical_games:
                if cg_key not in games_dict:
                    cg_views = []
                    expected_subpaths = get_symmetric_subpaths_for_subcat("Default", gen_num, has_female=(gen_num >= 4))
                    for subp in expected_subpaths:
                        folder_rel = f"sprites/pokemon/versions/{gen_id}/{cg_key}/{subp}".rstrip("/")
                        cg_views.append({
                            "label": format_subpath_label(subp, is_icon=False),
                            "folder": folder_rel,
                            "ext": ".png",
                            "subpath": subp,
                            "subcategory": "Default",
                            "female": "female" in subp.split("/"),
                        })
                    if gen_num >= 7:
                        cg_views.append({
                            "label": "Menu Icon",
                            "folder": f"sprites/pokemon/versions/{gen_id}/{cg_key}/icons",
                            "ext": ".png",
                            "subpath": "icons",
                            "subcategory": "Icons",
                            "female": False,
                        })
                        if gen_num >= 4:
                            cg_views.append({
                                "label": "Menu Icon (Female)",
                                "folder": f"sprites/pokemon/versions/{gen_id}/{cg_key}/icons/female",
                                "ext": ".png",
                                "subpath": "icons/female",
                                "subcategory": "Icons",
                                "female": True,
                            })
                    games_dict[cg_key] = cg_views

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
                has_female = gen_num >= 4
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

                views.sort(key=lambda v: subpath_sort_key(v["subpath"]))
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
                    "gen_num": gen_num,
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
    items_dict: dict[str, list[str]] = defaultdict(list)
    if base_items.exists():
        for p in base_items.rglob("*.png"):
            items_dict[p.stem].append(p.relative_to(base_items).as_posix())

    # 8. Types
    base_types = SPRITES_DIR / "types"
    types_dict: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    if base_types.exists():
        for p in base_types.rglob("*.png"):
            parts = p.relative_to(base_types).as_posix().split("/")
            if len(parts) >= 3:
                types_dict[parts[0]][parts[1]].append("/".join(parts[2:]))

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
        "types_list": types_list,
        "game_indices": game_indices,
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
