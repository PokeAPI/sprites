import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageFile

from common import (
    BASE_PATH,
    GITHUB_BASE_URL,
    PROJECT_ROOT,
    SCRIPT_DIR,
    TEMPLATES_DIR,
    WEBSITE_DIR,
    load_csv,
    reconfigure_utf8,
)

reconfigure_utf8()

# CATEGORY REGISTRY (Dynamically discovered from repository directories)
def discover_categories(base_path: Path) -> dict[str, dict[str, Any]]:
    """Dynamically registers default root category and discovers all subcategories in sprites/pokemon/other/."""
    categories: dict[str, dict[str, Any]] = {
        "default": {
            "name": "Root Sprites (Default)",
            "description": "Root /sprites/pokemon/ default pixel sprites (Gen 5 style)",
            "paths": {
                "Front": base_path,
                "Front Shiny": base_path / "shiny",
                "Back": base_path / "back",
                "Back Shiny": base_path / "back" / "shiny",
            },
            "female_paths": {
                "Front Female": base_path / "female",
                "Front Shiny Female": base_path / "shiny" / "female",
                "Back Female": base_path / "back" / "female",
                "Back Shiny Female": base_path / "back" / "shiny" / "female",
            },
            "extensions": [".png"],
            "check_dimensions": True,
        }
    }

    other_dir = base_path / "other"
    if not other_dir.exists():
        return categories

    category_descriptions = {
        "official-artwork": "High-resolution Pokémon official artwork renders",
        "home": "3D render sprites from Pokémon HOME",
        "showdown": "Animated GIF battle sprites from Pokémon Showdown",
        "dream-world": "Vector artwork from the Pokémon Global Link Dream World",
    }

    category_titles = {
        "official-artwork": "Official Artwork",
        "home": "Pokémon HOME",
        "showdown": "Showdown (Animated)",
        "dream-world": "Dream World",
    }

    for cat_folder in sorted(other_dir.iterdir()):
        if not cat_folder.is_dir():
            continue

        cat_key = cat_folder.name
        cat_name = category_titles.get(cat_key, cat_key.replace("-", " ").title())
        cat_desc = category_descriptions.get(cat_key, f"Sprites and assets from {cat_name}")

        paths: dict[str, Path] = {"Front": cat_folder}
        if (cat_folder / "shiny").is_dir():
            paths["Front Shiny"] = cat_folder / "shiny"
        if (cat_folder / "back").is_dir():
            paths["Back"] = cat_folder / "back"
        if (cat_folder / "back" / "shiny").is_dir():
            paths["Back Shiny"] = cat_folder / "back" / "shiny"

        female_paths: dict[str, Path] = {}
        if (cat_folder / "female").is_dir():
            female_paths["Front Female"] = cat_folder / "female"
        if (cat_folder / "shiny" / "female").is_dir():
            female_paths["Front Shiny Female"] = cat_folder / "shiny" / "female"
        if (cat_folder / "back" / "female").is_dir():
            female_paths["Back Female"] = cat_folder / "back" / "female"
        if (cat_folder / "back" / "shiny" / "female").is_dir():
            female_paths["Back Shiny Female"] = cat_folder / "back" / "shiny" / "female"

        # Detect extensions present in this category
        detected_exts = set()
        for f in cat_folder.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
                detected_exts.add(f.suffix.lower())

        extensions = sorted(list(detected_exts)) if detected_exts else [".png"]
        # SVGs and GIFs are scalable or animations with varying frame dimensions; static raster images check dimensions
        check_dimensions = not any(ext in (".svg", ".gif") for ext in extensions)

        categories[cat_key] = {
            "name": cat_name,
            "description": cat_desc,
            "paths": paths,
            "female_paths": female_paths,
            "extensions": extensions,
            "check_dimensions": check_dimensions,
        }

    return categories


CATEGORIES: dict[str, dict[str, Any]] = discover_categories(BASE_PATH)


def get_standard_dimension(
    category_paths: dict[str, Path],
    female_paths: dict[str, Path],
    extensions: list[str],
    sample_limit: int = 50,
) -> tuple[int, int] | None:
    """Scans sample files in a category to find the most common image size."""
    all_sizes: list[tuple[int, int]] = []
    valid_ext = tuple(ext.lower() for ext in extensions)

    all_folders = list(category_paths.values()) + list(female_paths.values())
    for folder in all_folders:
        if not folder.exists():
            continue
        count = 0
        for file in folder.glob("*"):
            if file.is_file() and file.suffix.lower() in valid_ext:
                try:
                    with Image.open(file) as img:
                        all_sizes.append(img.size)
                        count += 1
                        if count >= sample_limit:
                            break
                except Exception:
                    continue

    if not all_sizes:
        return None

    most_common: tuple[int, int] = Counter(all_sizes).most_common(1)[0][0]
    return most_common


def attempt_repair(path: Path) -> bool:
    """Try to repair an unreadable or corrupt image using ImageMagick -strip or Pillow.

    Returns True if the file was successfully repaired, False otherwise.
    """
    # 1. Try ImageMagick -strip (removes bad/corrupted iCCP / EXIF metadata chunks)
    try:
        res = subprocess.run(["magick", "mogrify", "-strip", str(path)], capture_output=True)
        if res.returncode == 0:
            with Image.open(path) as test_im:
                test_im.load()
            return True
    except Exception:
        pass

    # 2. Fallback to Pillow load truncated and re-save
    try:
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        with Image.open(path) as im:
            im.load()
            with tempfile.NamedTemporaryFile(delete=False, suffix=path.suffix) as tf:
                tmpname = tf.name
            im.save(tmpname, format=im.format or "PNG")
            shutil.move(tmpname, str(path))
        return True
    except Exception as ex:
        print(f"    [REPAIR FAILED] {path.name}: {ex}")
        try:
            if "tmpname" in locals() and Path(tmpname).exists():
                Path(tmpname).unlink()
        except Exception:
            pass
        return False


def write_csv_report(filepath: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Writes a list of dictionaries to a CSV file using Python stdlib."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            row_dict = {}
            for k in fieldnames:
                v = r.get(k, "")
                if isinstance(v, list):
                    v = ", ".join(str(x) for x in v)
                row_dict[k] = v
            writer.writerow(row_dict)


def scan_category(
    category_key: str,
    category_info: dict[str, Any],
    pokemon_entries: list[dict[str, Any]],
    form_entries: list[dict[str, Any]],
    include_forms: bool = False,
    collect_corrupts: bool = False,
) -> tuple[list[dict[str, Any]], set[Path], int, int, int, int, int]:
    """Scan a category for Pokémon varieties, female variants, and optional cosmetic forms.

    Returns:
        (grouped_issues, corrupt_paths, total_asset_targets, passed_asset_targets, total_missing, total_wrong_size, total_corrupt)
    """
    category_name: str = category_info["name"]
    paths: dict[str, Path] = category_info["paths"]
    female_paths: dict[str, Path] = category_info.get("female_paths", {})
    extensions: list[str] = category_info["extensions"]
    check_dimensions: bool = category_info["check_dimensions"]

    standard_size: tuple[int, int] | None = None
    if check_dimensions:
        standard_size = get_standard_dimension(paths, female_paths, extensions)
        if standard_size:
            print(f"  Standard dimension: {standard_size[0]}x{standard_size[1]}")
        else:
            print("  [WARN] Could not determine standard dimension; skipping dimension checks.")

    grouped_issues: list[dict[str, Any]] = []
    corrupt_paths: set[Path] = set()
    total_asset_targets = 0
    passed_asset_targets = 0
    total_missing = 0
    total_wrong_size = 0
    total_corrupt = 0

    # In-memory folder file cache to avoid thousands of disk stat calls on Windows
    folder_cache: dict[Path, set[str]] = {}
    all_check_folders = list(paths.values()) + list(female_paths.values())
    for fld in all_check_folders:
        folder_cache[fld] = {f.name for f in fld.iterdir() if f.is_file()} if fld.is_dir() else set()

    entries = pokemon_entries + (form_entries if include_forms else [])
    for p in entries:
        is_form = 1 if p.get("is_form") else 0
        p_id = p.get("pokemon_id", p.get("id"))
        f_id = p.get("form_id", p.get("id")) if is_form else ""
        name = p.get("name", p.get("identifier", ""))
        s_id = p.get("species_id", p_id)
        has_gender_diff = 1 if (p.get("has_gender_diff") or p.get("has_gender_differences")) else 0

        candidate_stems = list(p.get("candidate_stems", []))
        if not candidate_stems:
            form_ident = p.get("form_identifier", "")
            candidate_stems = [f"{p_id}-{form_ident}"] if (is_form and form_ident) else [str(f_id if is_form else p_id)]
        if is_form and name and name not in candidate_stems:
            candidate_stems.append(name)

        missing_types: list[str] = []
        wrong_size_types: list[str] = []
        corrupt_types: list[str] = []

        slots_to_check: list[tuple[str, Path]] = list(paths.items())
        if has_gender_diff and female_paths:
            slots_to_check.extend(female_paths.items())

        for sprite_label, folder in slots_to_check:
            total_asset_targets += 1
            found_path: Path | None = None
            files_in_folder = folder_cache.get(folder, set())

            for stem in candidate_stems:
                for ext in extensions:
                    fname = f"{stem}{ext}"
                    if fname in files_in_folder:
                        found_path = folder / fname
                        break
                if found_path:
                    break

            if not found_path:
                missing_types.append(sprite_label)
                total_missing += 1
            else:
                issue_found = False
                if found_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif"):
                    try:
                        with Image.open(found_path) as img:
                            if check_dimensions and standard_size and img.size != standard_size:
                                wrong_size_types.append(f"{sprite_label} ({img.size[0]}x{img.size[1]})")
                                total_wrong_size += 1
                                issue_found = True
                    except Exception:
                        if collect_corrupts:
                            corrupt_paths.add(found_path)
                        corrupt_types.append(sprite_label)
                        total_corrupt += 1
                        issue_found = True

                if not issue_found:
                    passed_asset_targets += 1

        if missing_types or wrong_size_types or corrupt_types:
            summary_parts: list[str] = []
            if missing_types:
                summary_parts.append(f"Missing: {', '.join(missing_types)}")
            if wrong_size_types:
                summary_parts.append(f"Wrong Size: {', '.join(wrong_size_types)}")
            if corrupt_types:
                summary_parts.append(f"Corrupt: {', '.join(corrupt_types)}")

            grouped_issues.append({
                "category": category_key,
                "category_name": category_name,
                "pokemon_id": p_id,
                "form_id": f_id,
                "identifier": name,
                "species_id": s_id,
                "is_form": is_form,
                "has_gender_differences": has_gender_diff,
                "missing_sprites": missing_types,
                "wrong_size_sprites": wrong_size_types,
                "corrupt_sprites": corrupt_types,
                "missing_str": ", ".join(missing_types),
                "wrong_size_str": ", ".join(wrong_size_types),
                "corrupt_str": ", ".join(corrupt_types),
                "issue_summary": " | ".join(summary_parts),
                "issues_count": len(missing_types) + len(wrong_size_types) + len(corrupt_types),
                "total_expected": len(slots_to_check),
            })

    return (
        grouped_issues,
        corrupt_paths,
        total_asset_targets,
        passed_asset_targets,
        total_missing,
        total_wrong_size,
        total_corrupt,
    )


def audit_version_sprites(
    include_forms: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], int, int, int]:
    """Audits version-specific sprites across all generations and core games using sprite_index.json."""
    index_path = WEBSITE_DIR / "data" / "sprite_index.json"
    if not index_path.exists():
        print("[INFO] sprite_index.json not found, generating manifest...")
        from build_sprite_index import build_index
        build_index()

    with open(index_path, encoding="utf-8") as f:
        data = json.load(f)

    folder_sets = {k: set(v) for k, v in data.get("folder_files", {}).items()}

    # Load per-game pokemon set from precomputed sprite_index.json (or fallback to stdlib CSV load)
    game_pokemon_ids: dict[str, set[int]] = {}
    if "game_indices" in data:
        game_pokemon_ids = {k: set(v) for k, v in data["game_indices"].items()}
        print(f"[INFO] Loaded precomputed game indices for {len(game_pokemon_ids)} version groups from sprite_index.json.")
    else:
        try:
            gi_rows = load_csv(f"{GITHUB_BASE_URL}/pokemon_game_indices.csv")
            v_rows = load_csv(f"{GITHUB_BASE_URL}/versions.csv")
            vg_rows = load_csv(f"{GITHUB_BASE_URL}/version_groups.csv")
            v_to_vg = {r["id"]: r["version_group_id"] for r in v_rows}
            vg_ident = {r["id"]: r["identifier"] for r in vg_rows}
            for r in gi_rows:
                vg_id = v_to_vg.get(r.get("version_id", ""))
                if vg_id:
                    vg_key = vg_ident.get(vg_id)
                    if vg_key and r.get("pokemon_id"):
                        game_pokemon_ids.setdefault(vg_key, set()).add(int(r["pokemon_id"]))

            if "black-2-white-2" in game_pokemon_ids:
                game_pokemon_ids.setdefault("black-white", set()).update(game_pokemon_ids["black-2-white-2"])
            if "sun-moon" in game_pokemon_ids:
                game_pokemon_ids.setdefault("ultra-sun-ultra-moon", set()).update(game_pokemon_ids["sun-moon"])

            print(f"[INFO] Loaded game indices for {len(game_pokemon_ids)} version groups via CSV.")
        except Exception as e:
            print(f"[WARN] Could not load game indices ({e}); falling back to generation-based filtering.")

    total_targets = 0
    total_passed = 0
    total_missing = 0
    game_stats: dict[str, dict[str, Any]] = {}
    all_version_issues: list[dict[str, Any]] = []

    pokemon_list = data.get("pokemon_list", [])
    if not include_forms:
        pokemon_list = [p for p in pokemon_list if not p.get("is_form", False)]

    def check_has_sprite(folder_name: str, p_entry: dict[str, Any]) -> bool:
        f_set = folder_sets.get(folder_name, set())
        stems = p_entry.get("candidate_stems", [str(p_entry["id"])])
        for s in stems:
            if s in f_set or (s.isdigit() and int(s) in f_set):
                return True
        return False

    for gen in data.get("generations", []):
        gen_id = gen.get("id", "")
        gen_title = gen.get("title", "")
        gen_num = gen.get("gen_num", 1)

        # 1. Audit core games
        for game in gen.get("games", []):
            game_name = game.get("name", "")
            game_folder = game.get("folder", "")
            game_id = Path(game_folder).name
            views = game.get("views", [])
            if not views:
                continue

            g_targets = 0
            g_passed = 0
            g_missing = 0
            g_issues_count = 0

            indexed_ids = game_pokemon_ids.get(game_id)
            game_pokemon = []
            for p in pokemon_list:
                p_base_id = p.get("pokemon_id", p["id"])
                p_gen = p.get("generation_id", 1)
                has_files_in_game = any(check_has_sprite(v.get("folder", ""), p) for v in views)

                if indexed_ids is not None:
                    # In game if base variety is indexed AND form/variety has debuted on or before this generation,
                    # OR if assets physically exist in this game's folder
                    if (p_base_id in indexed_ids and p_gen <= gen_num) or has_files_in_game:
                        game_pokemon.append(p)
                else:
                    if p_gen <= gen_num or has_files_in_game:
                        game_pokemon.append(p)

            for p in game_pokemon:
                p_id = p["id"]
                p_name = p["name"]
                is_dimorphic = bool(p.get("has_gender_diff", False))

                missing_for_p: list[str] = []
                checked_for_p = 0

                for v in views:
                    if v.get("female", False) and not is_dimorphic:
                        continue

                    v_folder = v.get("folder", "")
                    g_targets += 1
                    checked_for_p += 1

                    if check_has_sprite(v_folder, p):
                        g_passed += 1
                    else:
                        g_missing += 1
                        missing_for_p.append(v.get("label", "Unknown View"))

                if missing_for_p:
                    g_issues_count += 1
                    all_version_issues.append({
                        "gen_id": gen_id,
                        "gen_name": gen_title,
                        "gen_num": gen_num,
                        "game_id": game_id,
                        "game_name": game_name,
                        "pokemon_id": p.get("pokemon_id", p["id"]),
                        "form_id": p.get("form_id", "") if p.get("is_form") else "",
                        "identifier": p_name,
                        "is_form": 1 if p.get("is_form") else 0,
                        "has_gender_differences": 1 if is_dimorphic else 0,
                        "missing_sprites": missing_for_p,
                        "missing_count": len(missing_for_p),
                        "total_expected": checked_for_p,
                        "missing_str": ", ".join(missing_for_p),
                    })

            pct = (g_passed / g_targets * 100) if g_targets > 0 else 0
            game_stats[game_id] = {
                "gen_id": gen_id,
                "gen_name": gen_title,
                "gen_num": gen_num,
                "game_id": game_id,
                "game_name": game_name,
                "total_targets": g_targets,
                "passed_targets": g_passed,
                "missing_targets": g_missing,
                "affected_entries": g_issues_count,
                "completion_rate": round(pct, 2),
            }
            total_targets += g_targets
            total_passed += g_passed
            total_missing += g_missing

        # 2. Audit generation-level icons (e.g. Gen 5, Gen 7, Gen 8)
        gen_icons = gen.get("icons", [])
        if gen_icons:
            icon_key = f"{gen_id}-icons"
            icon_name = f"{gen_title} Icons"
            i_targets = 0
            i_passed = 0
            i_missing = 0
            i_issues_count = 0

            for p in pokemon_list:
                p_name = p["name"]
                p_gen = p.get("generation_id", 1)
                is_dimorphic = bool(p.get("has_gender_diff", False))

                has_files = any(check_has_sprite(icon.get("folder", ""), p) for icon in gen_icons)

                if p_gen > gen_num and not has_files:
                    continue

                missing_for_p = []
                checked_for_p = 0

                for icon in gen_icons:
                    if "female" in icon.get("label", "").lower() and not is_dimorphic:
                        continue

                    folder = icon.get("folder", "")
                    i_targets += 1
                    checked_for_p += 1

                    if check_has_sprite(folder, p):
                        i_passed += 1
                    else:
                        i_missing += 1
                        missing_for_p.append(icon.get("label", "Menu Icon"))

                if missing_for_p:
                    i_issues_count += 1
                    all_version_issues.append({
                        "gen_id": gen_id,
                        "gen_name": gen_title,
                        "gen_num": gen_num,
                        "game_id": icon_key,
                        "game_name": icon_name,
                        "pokemon_id": p.get("pokemon_id", p["id"]),
                        "form_id": p.get("form_id", "") if p.get("is_form") else "",
                        "identifier": p_name,
                        "is_form": 1 if p.get("is_form") else 0,
                        "has_gender_differences": 1 if is_dimorphic else 0,
                        "missing_sprites": missing_for_p,
                        "missing_count": len(missing_for_p),
                        "total_expected": checked_for_p,
                        "missing_str": ", ".join(missing_for_p),
                    })

            pct = (i_passed / i_targets * 100) if i_targets > 0 else 0
            game_stats[icon_key] = {
                "gen_id": gen_id,
                "gen_name": gen_title,
                "gen_num": gen_num,
                "game_id": icon_key,
                "game_name": icon_name,
                "total_targets": i_targets,
                "passed_targets": i_passed,
                "missing_targets": i_missing,
                "affected_entries": i_issues_count,
                "completion_rate": round(pct, 2),
            }
            total_targets += i_targets
            total_passed += i_passed
            total_missing += i_missing

    return game_stats, all_version_issues, total_targets, total_passed, total_missing


def generate_html_report(
    grouped_issues: list[dict[str, Any]],
    stats_by_category: dict[str, dict[str, Any]],
    total_asset_targets: int,
    total_passed_assets: int,
    total_missing_assets: int,
    total_wrong_size_assets: int,
    total_corrupt_assets: int,
    output_path: Path,
    version_stats: dict[str, dict[str, Any]] | None = None,
    version_issues: list[dict[str, Any]] | None = None,
    total_version_targets: int = 0,
    total_version_passed: int = 0,
    total_version_missing: int = 0,
    standalone: bool = False,
) -> None:
    """Generates the interactive HTML audit dashboard using the template in scripts/tracker/templates/."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completion_rate = round((total_passed_assets / total_asset_targets * 100), 2) if total_asset_targets > 0 else 100.0
    version_completion_rate = round((total_version_passed / total_version_targets * 100), 2) if total_version_targets > 0 else 100.0

    template_file = TEMPLATES_DIR / "audit_dashboard.html"
    if not template_file.exists():
        raise FileNotFoundError(f"HTML Template not found at: {template_file}")

    if not standalone:
        data_dir = WEBSITE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / "audit_data.json", "w", encoding="utf-8") as f:
            json.dump(grouped_issues, f, separators=(",", ":"))
        with open(data_dir / "version_audit_data.json", "w", encoding="utf-8") as f:
            json.dump(version_issues or [], f, separators=(",", ":"))
        print(f"[DATA] Externalized datasets to {data_dir / 'audit_data.json'} and {data_dir / 'version_audit_data.json'}")

    fmt_pct = lambda r: f"{r:.2f}".rstrip("0").rstrip(".") if r != 100 else "100"
    ctx = {
        "completion_rate": fmt_pct(completion_rate),
        "total_passed_assets": f"{total_passed_assets:,}",
        "total_asset_targets": f"{total_asset_targets:,}",
        "affected_entries_count": f"{len(grouped_issues):,}",
        "total_missing_assets": f"{total_missing_assets:,}",
        "total_wrong_size_assets": f"{total_wrong_size_assets:,}",
        "total_corrupt_assets": f"{total_corrupt_assets:,}",
        "categories_json": json.dumps(stats_by_category),
        "issues_json": json.dumps(grouped_issues) if standalone else "null",
        "version_completion_rate": fmt_pct(version_completion_rate),
        "total_version_passed": f"{total_version_passed:,}",
        "total_version_targets": f"{total_version_targets:,}",
        "total_version_missing": f"{total_version_missing:,}",
        "version_affected_entries_count": f"{len(version_issues or []):,}",
        "version_stats_json": json.dumps(version_stats or {}),
        "version_issues_json": json.dumps(version_issues or []) if standalone else "null",
    }

    try:
        from jinja2 import Environment, FileSystemLoader
        rendered_html = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False).get_template("audit_dashboard.html").render(**ctx)
    except ImportError:
        rendered_html = template_file.read_text(encoding="utf-8")
        for k, v in ctx.items():
            rendered_html = rendered_html.replace(f"{{{{ {k} }}}}", str(v))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)
    print(f"[REPORT] HTML Report written to: {output_path}")


def check_assets(
    category: str = "all",
    include_forms: bool = False,
    repair_enabled: bool = False,
    html_out: str | None = None,
    csv_out: str | None = None,
    no_csv: bool = False,
    standalone: bool = False,
) -> None:
    """Executes the asset audit across specified categories and outputs reports."""
    print("\n" + "=" * 60)
    print("POKÉMON SPRITE AUDIT DASHBOARD")
    print(f"Script   : {Path(__file__).name}")
    print(f"Target   : {BASE_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Category : {category.upper()}")
    print(f"Cosmetic Forms : {'YES' if include_forms else 'NO'}")
    print(f"Repair Mode    : {'ENABLED' if repair_enabled else 'DISABLED'}")
    print("Version Sprites: Audited across Gen I-IX core games & menu icons.")
    print("=" * 60 + "\n")

    # 1. Load Pokémon entity manifest from sprite_index.json (auto-build if missing)
    index_path = WEBSITE_DIR / "data" / "sprite_index.json"
    if not index_path.exists():
        print("[INFO] sprite_index.json not found, generating manifest...")
        from build_sprite_index import build_index
        build_index()

    with open(index_path, encoding="utf-8") as f:
        manifest_data = json.load(f)

    all_entities = manifest_data.get("pokemon_list", [])
    pokemon_entries = [p for p in all_entities if not p.get("is_form", False)]
    form_entries = [p for p in all_entities if p.get("is_form", False)] if include_forms else []

    # 2. Determine target categories
    target_categories: dict[str, dict[str, Any]] = {}
    audit_versions = category.lower() in ("all", "versions")

    if category.lower() == "all":
        target_categories = CATEGORIES
    elif category.lower() in CATEGORIES:
        target_categories = {category.lower(): CATEGORIES[category.lower()]}
    elif category.lower() == "versions":
        target_categories = {}
    else:
        print(f"[ERROR] Invalid category '{category}'. Available: {list(CATEGORIES.keys())}, 'versions', or 'all'")
        return

    all_grouped_issues: list[dict[str, Any]] = []
    stats_by_category: dict[str, dict[str, Any]] = {}
    grand_total_targets = 0
    grand_total_passed = 0
    grand_total_missing = 0
    grand_total_wrong_size = 0
    grand_total_corrupt = 0

    # 3. Execute Audits per category
    for cat_key, cat_info in target_categories.items():
        print(f"\n[SCAN] Scanning Category: {cat_info['name']}...")
        (
            cat_issues,
            corrupt_paths,
            cat_targets,
            cat_passed,
            cat_missing,
            cat_wrong_size,
            cat_corrupt,
        ) = scan_category(
            category_key=cat_key,
            category_info=cat_info,
            pokemon_entries=pokemon_entries,
            form_entries=form_entries,
            include_forms=include_forms,
            collect_corrupts=repair_enabled,
        )

        if repair_enabled and corrupt_paths:
            print(f"  [REPAIR] Attempting repair for {len(corrupt_paths)} corrupt files in {cat_info['name']}...")
            for path in sorted(corrupt_paths):
                success = attempt_repair(path)
                status_label = "REPAIRED" if success else "FAILED"
                print(f"    [{status_label}] {path.name}")
            # Re-scan category after repair pass
            (
                cat_issues,
                _,
                cat_targets,
                cat_passed,
                cat_missing,
                cat_wrong_size,
                cat_corrupt,
            ) = scan_category(
                category_key=cat_key,
                category_info=cat_info,
                pokemon_entries=pokemon_entries,
                form_entries=form_entries,
                include_forms=include_forms,
                collect_corrupts=False,
            )

        all_grouped_issues.extend(cat_issues)
        grand_total_targets += cat_targets
        grand_total_passed += cat_passed
        grand_total_missing += cat_missing
        grand_total_wrong_size += cat_wrong_size
        grand_total_corrupt += cat_corrupt

        flawed_targets = cat_targets - cat_passed
        stats_by_category[cat_key] = {
            "name": cat_info["name"],
            "description": cat_info["description"],
            "total_targets": cat_targets,
            "passed_targets": cat_passed,
            "flawed_targets": flawed_targets,
            "missing_targets": cat_missing,
            "wrong_size_targets": cat_wrong_size,
            "corrupt_targets": cat_corrupt,
            "affected_entries": len(cat_issues),
        }
        print(f"  Result: {len(cat_issues)} affected entries ({flawed_targets:,} flawed files) out of {cat_targets:,} asset targets.")

    # 4. Audit Game Version Sprites (if requested)
    version_stats: dict[str, dict[str, Any]] = {}
    all_version_issues: list[dict[str, Any]] = []
    v_targets = 0
    v_passed = 0
    v_missing = 0

    if audit_versions:
        print("\n[SCAN] Auditing Game Version Sprites across Generations I through IX...")
        version_stats, all_version_issues, v_targets, v_passed, v_missing = audit_version_sprites(
            include_forms=include_forms
        )
        v_pct = round((v_passed / v_targets * 100), 2) if v_targets > 0 else 100.0
        print(f"  Result: {v_passed:,} passed / {v_targets:,} targets ({v_pct}%), {len(all_version_issues):,} affected entries.")

    # 5. Save Grouped CSV Reports
    if not no_csv:
        csv_file = Path(csv_out) if csv_out else (SCRIPT_DIR / "sprite_audit_report.csv")
        ARTWORK_CSV_FIELDS = [
            "category",
            "category_name",
            "pokemon_id",
            "form_id",
            "identifier",
            "species_id",
            "is_form",
            "has_gender_differences",
            "missing_sprites",
            "wrong_size_sprites",
            "corrupt_sprites",
            "issue_summary",
        ]
        csv_rows: list[dict[str, Any]] = []
        for item in all_grouped_issues:
            csv_rows.append({
                "category": item["category"],
                "category_name": item["category_name"],
                "pokemon_id": item["pokemon_id"],
                "form_id": item["form_id"],
                "identifier": item["identifier"],
                "species_id": item["species_id"],
                "is_form": item["is_form"],
                "has_gender_differences": item["has_gender_differences"],
                "missing_sprites": item["missing_str"],
                "wrong_size_sprites": item["wrong_size_str"],
                "corrupt_sprites": item["corrupt_str"],
                "issue_summary": item["issue_summary"],
            })
        csv_rows.sort(key=lambda x: (x.get("category", ""), int(x.get("pokemon_id") or 0)))
        write_csv_report(csv_file, csv_rows, ARTWORK_CSV_FIELDS)
        if all_grouped_issues:
            print(f"\n[REPORT] Artwork CSV Report saved to: {csv_file}")
        else:
            print(f"\n[OK] Zero artwork issues found! CSV report saved to: {csv_file}")

        # Export version CSV
        if audit_versions:
            version_csv_file = SCRIPT_DIR / "sprite_audit_versions.csv"
            VERSION_CSV_FIELDS = [
                "gen_id",
                "gen_name",
                "gen_num",
                "game_id",
                "game_name",
                "pokemon_id",
                "form_id",
                "identifier",
                "is_form",
                "has_gender_differences",
                "missing_count",
                "total_expected",
                "missing_sprites",
            ]
            write_csv_report(version_csv_file, all_version_issues, VERSION_CSV_FIELDS)
            if all_version_issues:
                print(f"[REPORT] Version Sprites CSV Report saved to: {version_csv_file}")
            else:
                print(f"[OK] Zero version issues found! Version CSV saved to: {version_csv_file}")

    # 6. Save HTML Dashboard
    html_target = Path(html_out) if html_out else (WEBSITE_DIR / "audit.html")
    generate_html_report(
        grouped_issues=all_grouped_issues,
        stats_by_category=stats_by_category,
        total_asset_targets=grand_total_targets,
        total_passed_assets=grand_total_passed,
        total_missing_assets=grand_total_missing,
        total_wrong_size_assets=grand_total_wrong_size,
        total_corrupt_assets=grand_total_corrupt,
        output_path=html_target,
        version_stats=version_stats,
        version_issues=all_version_issues,
        total_version_targets=v_targets,
        total_version_passed=v_passed,
        total_version_missing=v_missing,
        standalone=standalone,
    )

    # If writing to website folder and standalone, ensure CSVs are mirrored
    if html_target.parent == WEBSITE_DIR and not no_csv:
        website_csv = WEBSITE_DIR / "audit_report.csv"
        if csv_file.exists():
            shutil.copyfile(csv_file, website_csv)
        if audit_versions and version_csv_file.exists():
            website_v_csv = WEBSITE_DIR / "audit_report_versions.csv"
            shutil.copyfile(version_csv_file, website_v_csv)

    # 7. Console Summary
    if target_categories:
        print("\n" + "=" * 60)
        print("MODERN & ARTWORK COLLECTIONS AUDIT SUMMARY")
        print("=" * 60)
        print(f"Total Asset Targets    : {grand_total_targets:>8,}")
        print(f"Total Passed Assets    : {grand_total_passed:>8,}")
        flawed_total = grand_total_targets - grand_total_passed
        print(f"Total Flawed Assets    : {flawed_total:>8,}")
        completion = round((grand_total_passed / grand_total_targets * 100), 2) if grand_total_targets > 0 else 100.0
        print(f"Asset Completion Rate  : {completion:>7}%")
        print(f"Total Affected Entries : {len(all_grouped_issues):>8,} Pokémon/forms")
        print("-" * 60)
        print(f"  - Missing files      : {grand_total_missing:>8,}")
        print(f"  - Wrong dimensions   : {grand_total_wrong_size:>8,}")
        print(f"  - Corrupt files      : {grand_total_corrupt:>8,}")
        print("=" * 60)

    if audit_versions:
        print("\n" + "=" * 60)
        print("GAME VERSION SPRITES AUDIT SUMMARY (GEN I - IX)")
        print("=" * 60)
        print(f"Total Version Targets  : {v_targets:>8,}")
        print(f"Total Passed Sprites   : {v_passed:>8,}")
        print(f"Total Missing Sprites  : {v_missing:>8,}")
        v_completion = round((v_passed / v_targets * 100), 2) if v_targets > 0 else 100.0
        print(f"Version Completion Rate: {v_completion:>7}%")
        print(f"Affected Pokémon Entries: {len(all_version_issues):>8,} Pokémon/game combinations")
        print("=" * 60 + "\n")


def parse_args_and_run() -> None:
    """Parses command line arguments and runs audit."""
    parser = argparse.ArgumentParser(description="Audit Pokémon Sprites across categories and formats")
    parser.add_argument(
        "--category",
        choices=["default", "official-artwork", "home", "showdown", "dream-world", "versions", "all"],
        default="all",
        help="Sprite category to audit (default: 'all')",
    )
    parser.add_argument(
        "--include-forms",
        action="store_true",
        help="Audit non-default cosmetic forms (e.g. Sinistea Antique, Vivillon patterns, Unown forms)",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Attempt to repair corrupt images using ImageMagick -strip or Pillow",
    )
    parser.add_argument(
        "-o",
        "--output",
        "--html",
        dest="html",
        type=str,
        default=None,
        help="File path for the HTML dashboard (default: website/audit.html)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="File path for the CSV report (default: scripts/sprite_audit_report.csv)",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip CSV report generation",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Embed entire dataset into HTML for offline single-file opening without a web server (defaults to external data/ JSON files)",
    )
    parser.add_argument(
        "--build-index",
        action="store_true",
        help="Build offline repository sprite index for Sprite Finder (website/data/sprite_index.json)",
    )

    args = parser.parse_args()
    check_assets(
        category=args.category,
        include_forms=args.include_forms,
        repair_enabled=args.repair,
        html_out=args.html,
        csv_out=args.csv,
        no_csv=args.no_csv,
        standalone=args.standalone,
    )

    if args.build_index:
        from build_sprite_index import build_index
        build_index()


if __name__ == "__main__":
    parse_args_and_run()