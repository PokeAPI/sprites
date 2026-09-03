import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import  Dict, List, Optional, Set, Tuple

import pandas as pd
from PIL import Image, ImageFile

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# CONFIGURATION
GITHUB_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
POKEMON_CSV_URL = f"{GITHUB_BASE_URL}/pokemon.csv"
FORMS_CSV_URL = f"{GITHUB_BASE_URL}/pokemon_forms.csv"
SPECIES_CSV_URL = f"{GITHUB_BASE_URL}/pokemon_species.csv"
VG_CSV_URL = f"{GITHUB_BASE_URL}/version_groups.csv"

# Local Sprite directories relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BASE_PATH = PROJECT_ROOT / "sprites" / "pokemon"
WEBSITE_DIR = PROJECT_ROOT / "website"
TEMPLATES_DIR = SCRIPT_DIR / "templates"

# CATEGORY REGISTRY
CATEGORIES = {
    "default": {
        "name": "Default (Pixel Art)",
        "description": "Standard Gen 5 Black & White style sprites",
        "paths": {
            "Front": BASE_PATH,
            "Front Shiny": BASE_PATH / "shiny",
            "Back": BASE_PATH / "back",
            "Back Shiny": BASE_PATH / "back" / "shiny",
        },
        "female_paths": {
            "Front Female": BASE_PATH / "female",
            "Front Shiny Female": BASE_PATH / "shiny" / "female",
            "Back Female": BASE_PATH / "back" / "female",
            "Back Shiny Female": BASE_PATH / "back" / "shiny" / "female",
        },
        "extensions": [".png"],
        "check_dimensions": True,
    },
    "official-artwork": {
        "name": "Official Artwork",
        "description": "High-resolution Pokémon official artwork renders",
        "paths": {
            "Front": BASE_PATH / "other" / "official-artwork",
            "Front Shiny": BASE_PATH / "other" / "official-artwork" / "shiny",
        },
        "female_paths": {},
        "extensions": [".png", ".jpg", ".jpeg"],
        "check_dimensions": True,
    },
    "home": {
        "name": "Pokémon HOME",
        "description": "3D render sprites from Pokémon HOME",
        "paths": {
            "Front": BASE_PATH / "other" / "home",
            "Front Shiny": BASE_PATH / "other" / "home" / "shiny",
        },
        "female_paths": {
            "Front Female": BASE_PATH / "other" / "home" / "female",
            "Front Shiny Female": BASE_PATH / "other" / "home" / "shiny" / "female",
        },
        "extensions": [".png"],
        "check_dimensions": True,
    },
    "showdown": {
        "name": "Showdown (Animated)",
        "description": "Animated GIF battle sprites from Pokémon Showdown",
        "paths": {
            "Front": BASE_PATH / "other" / "showdown",
            "Front Shiny": BASE_PATH / "other" / "showdown" / "shiny",
            "Back": BASE_PATH / "other" / "showdown" / "back",
            "Back Shiny": BASE_PATH / "other" / "showdown" / "back" / "shiny",
        },
        "female_paths": {
            "Front Female": BASE_PATH / "other" / "showdown" / "female",
            "Front Shiny Female": BASE_PATH / "other" / "showdown" / "shiny" / "female",
            "Back Female": BASE_PATH / "other" / "showdown" / "back" / "female",
            "Back Shiny Female": BASE_PATH / "other" / "showdown" / "back" / "shiny" / "female",
        },
        "extensions": [".gif"],
        "check_dimensions": False,
    },
    "dream-world": {
        "name": "Dream World",
        "description": "Vector artwork from the Pokémon Global Link Dream World",
        "paths": {
            "Front": BASE_PATH / "other" / "dream-world",
        },
        "female_paths": {
            "Front Female": BASE_PATH / "other" / "dream-world" / "female",
        },
        "extensions": [".svg", ".png"],
        "check_dimensions": False,
    },
}


def get_standard_dimension(category_paths: Dict[str, Path], female_paths: Dict[str, Path], extensions: List[str], sample_limit: int = 50) -> Optional[Tuple[int, int]]:
    """Scans sample files in a category to find the most common image size."""
    all_sizes = []
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

    most_common = Counter(all_sizes).most_common(1)[0][0]
    return most_common


def attempt_repair(path: Path) -> bool:
    """Try to repair an unreadable image by loading with truncated-images enabled and re-saving."""
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


def scan_category(
    category_key: str,
    category_info: dict,
    pokemon_entries: List[dict],
    form_entries: List[dict],
    include_forms: bool = False,
    collect_corrupts: bool = False,
) -> Tuple[List[dict], Set[Path], int, int, int, int, int]:
    """Scan a category for Pokémon varieties, female variants, and optional cosmetic forms.

    Returns:
        (grouped_issues, corrupt_paths, total_asset_targets, passed_asset_targets, total_missing, total_wrong_size, total_corrupt)
    """
    category_name = category_info["name"]
    paths = category_info["paths"]
    female_paths = category_info.get("female_paths", {})
    extensions = category_info["extensions"]
    check_dimensions = category_info["check_dimensions"]

    standard_size = None
    if check_dimensions:
        standard_size = get_standard_dimension(paths, female_paths, extensions)
        if standard_size:
            print(f"  Standard dimension: {standard_size[0]}x{standard_size[1]}")
        else:
            print(f"  [WARN] Could not determine standard dimension; skipping dimension checks.")

    grouped_issues = []
    corrupt_paths = set()
    total_asset_targets = 0
    passed_asset_targets = 0
    total_missing = 0
    total_wrong_size = 0
    total_corrupt = 0

    # 1. Scan Pokémon entries (Varieties)
    for p in pokemon_entries:
        p_id = p["pokemon_id"]
        s_id = p["species_id"]
        name = p["identifier"]
        gen = int(p["generation"]) if pd.notnull(p["generation"]) else "Unknown"
        has_gender_diff = int(p["has_gender_differences"]) if pd.notnull(p.get("has_gender_differences")) else 0

        missing_types = []
        wrong_size_types = []
        corrupt_types = []

        # Standard slots
        slots_to_check = list(paths.items())
        # Add female slots if species has gender differences
        if has_gender_diff and female_paths:
            slots_to_check.extend(female_paths.items())

        for sprite_label, folder in slots_to_check:
            total_asset_targets += 1
            found_path = None

            for ext in extensions:
                candidate = folder / f"{p_id}{ext}"
                if candidate.exists():
                    found_path = candidate
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
            summary_parts = []
            if missing_types:
                summary_parts.append(f"Missing: {', '.join(missing_types)}")
            if wrong_size_types:
                summary_parts.append(f"Wrong Size: {', '.join(wrong_size_types)}")
            if corrupt_types:
                summary_parts.append(f"Corrupt: {', '.join(corrupt_types)}")

            grouped_issues.append(
                {
                    "category": category_key,
                    "category_name": category_name,
                    "pokemon_id": p_id,
                    "form_id": "",
                    "identifier": name,
                    "species_id": s_id,
                    "generation": gen,
                    "is_form": 0,
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
                }
            )

    # 2. Scan Cosmetic Forms (if requested)
    if include_forms and form_entries:
        for f in form_entries:
            f_id = f["form_id"]
            p_id = f["pokemon_id"]
            s_id = f["species_id"]
            name = f["identifier"]
            form_ident = f["form_identifier"] if pd.notnull(f["form_identifier"]) else ""
            gen = int(f["generation"]) if pd.notnull(f["generation"]) else "Unknown"
            has_gender_diff = int(f["has_gender_differences"]) if pd.notnull(f.get("has_gender_differences")) else 0

            missing_types = []
            wrong_size_types = []
            corrupt_types = []

            slots_to_check = list(paths.items())
            if has_gender_diff and female_paths:
                slots_to_check.extend(female_paths.items())

            for sprite_label, folder in slots_to_check:
                total_asset_targets += 1
                found_path = None

                candidate_names = []
                for ext in extensions:
                    candidate_names.append(f"{f_id}{ext}")
                    if form_ident:
                        candidate_names.append(f"{p_id}-{form_ident}{ext}")
                    candidate_names.append(f"{name}{ext}")

                for c_name in candidate_names:
                    candidate = folder / c_name
                    if candidate.exists():
                        found_path = candidate
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
                summary_parts = []
                if missing_types:
                    summary_parts.append(f"Missing: {', '.join(missing_types)}")
                if wrong_size_types:
                    summary_parts.append(f"Wrong Size: {', '.join(wrong_size_types)}")
                if corrupt_types:
                    summary_parts.append(f"Corrupt: {', '.join(corrupt_types)}")

                grouped_issues.append(
                    {
                        "category": category_key,
                        "category_name": category_name,
                        "pokemon_id": p_id,
                        "form_id": f_id,
                        "identifier": name,
                        "species_id": s_id,
                        "generation": gen,
                        "is_form": 1,
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
                    }
                )

    return (
        grouped_issues,
        corrupt_paths,
        total_asset_targets,
        passed_asset_targets,
        total_missing,
        total_wrong_size,
        total_corrupt,
    )


def generate_html_report(
    grouped_issues: List[dict],
    stats_by_category: Dict[str, dict],
    total_asset_targets: int,
    total_passed_assets: int,
    total_missing_assets: int,
    total_wrong_size_assets: int,
    total_corrupt_assets: int,
    output_path: Path,
) -> None:
    """Generates the interactive HTML audit dashboard using the Jinja2 template in scripts/templates/."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completion_rate = round((total_passed_assets / total_asset_targets * 100), 2) if total_asset_targets > 0 else 100.0

    template_file = TEMPLATES_DIR / "audit_dashboard.html"
    if not template_file.exists():
        raise FileNotFoundError(f"HTML Template not found at: {template_file}")

    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
        template = env.get_template("audit_dashboard.html")
    except ImportError:
        # Fallback to simple placeholder replacement if jinja2 is unavailable
        template_text = template_file.read_text(encoding="utf-8")
        rendered_html = (
            template_text
            .replace("{{ completion_rate }}", f"{completion_rate:.2f}".rstrip("0").rstrip(".") if completion_rate != 100 else "100")
            .replace("{{ total_passed_assets }}", f"{total_passed_assets:,}")
            .replace("{{ total_asset_targets }}", f"{total_asset_targets:,}")
            .replace("{{ affected_entries_count }}", f"{len(grouped_issues):,}")
            .replace("{{ total_missing_assets }}", f"{total_missing_assets:,}")
            .replace("{{ total_wrong_size_assets }}", f"{total_wrong_size_assets:,}")
            .replace("{{ total_corrupt_assets }}", f"{total_corrupt_assets:,}")
            .replace("{{ categories_json }}", json.dumps(stats_by_category))
            .replace("{{ issues_json }}", json.dumps(grouped_issues))
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
        print(f"[REPORT] HTML Report written to: {output_path}")
        return

    rendered_html = template.render(
        completion_rate=f"{completion_rate:.2f}".rstrip("0").rstrip(".") if completion_rate != 100 else "100",
        total_passed_assets=f"{total_passed_assets:,}",
        total_asset_targets=f"{total_asset_targets:,}",
        affected_entries_count=f"{len(grouped_issues):,}",
        total_missing_assets=f"{total_missing_assets:,}",
        total_wrong_size_assets=f"{total_wrong_size_assets:,}",
        total_corrupt_assets=f"{total_corrupt_assets:,}",
        categories_json=json.dumps(stats_by_category),
        issues_json=json.dumps(grouped_issues),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)
    print(f"[REPORT] HTML Report written to: {output_path}")


def check_assets(
    category: str = "all",
    include_forms: bool = False,
    repair_enabled: bool = False,
    html_out: Optional[str] = None,
    csv_out: Optional[str] = None,
    no_csv: bool = False,
):
    print("\n" + "=" * 60)
    print("POKEMON SPRITE AUDIT DASHBOARD")
    print(f"Script: {Path(__file__).name}")
    print(f"Category: {category.upper()}")
    print(f"Include Cosmetic Forms: {'YES' if include_forms else 'NO'}")
    print(f"Repair Mode: {'ENABLED' if repair_enabled else 'DISABLED'}")
    print("=" * 60 + "\n")

    # 1. Load Data from GitHub
    print("[INFO] Fetching PokeAPI metadata from GitHub...")
    try:
        df_pokemon = pd.read_csv(POKEMON_CSV_URL)
        df_forms = pd.read_csv(FORMS_CSV_URL)
        df_species = pd.read_csv(SPECIES_CSV_URL)
        df_vg = pd.read_csv(VG_CSV_URL)
    except Exception as e:
        print(f"[ERROR] Failed fetching data: {e}")
        return

    # Process Pokémon entries
    df_forms_first = df_forms.sort_values(by=["pokemon_id", "id"]).drop_duplicates(subset=["pokemon_id"])
    df_merged = df_pokemon.merge(
        df_forms_first[["pokemon_id", "introduced_in_version_group_id", "form_identifier", "is_mega", "is_battle_only"]],
        left_on="id",
        right_on="pokemon_id",
        how="left",
    )
    df_merged = df_merged.merge(
        df_species[["id", "has_gender_differences"]].rename(
            columns={"has_gender_differences": "has_gender_diff_species"}
        ),
        left_on="species_id",
        right_on="id",
        how="left",
    )
    df_merged = df_merged.merge(
        df_vg[["id", "generation_id"]],
        left_on="introduced_in_version_group_id",
        right_on="id",
        how="left",
    )

    # Determine whether a Pokémon variety expects female sprite assets:
    # 1. Base canonical species (is_default == 1) whose species has gender differences.
    # 2. Dimorphic regional varieties (e.g. Hisuian Sneasel, form_identifier == "hisui").
    # Excludes: Megas (is_mega == 1), G-Max (is_battle_only == 1), dedicated female form entries (form_identifier == "female"),
    # Cosplay/Cap Pikachus, and non-dimorphic regional forms (Alolan Rattata, Paldean Wooper).
    def is_dimorphic_entry(r):
        if r.get("has_gender_diff_species") != 1:
            return 0
        if r.get("is_default") == 1:
            return 1
        # Regional forms of dimorphic species that retain sexual dimorphism (Hisuian Sneasel)
        if not r.get("is_mega") and not r.get("is_battle_only") and r.get("form_identifier") == "hisui":
            return 1
        return 0

    df_merged["has_gender_differences"] = df_merged.apply(is_dimorphic_entry, axis=1)

    df_entries = (
        df_merged[["id_x", "species_id", "identifier", "generation_id", "has_gender_differences"]]
        .rename(columns={"id_x": "pokemon_id", "generation_id": "generation"})
        .sort_values(by=["pokemon_id"])
    )
    pokemon_entries = df_entries.to_dict("records")

    # Process Cosmetic Forms entries
    form_entries = []
    if include_forms:
        df_forms_non_default = df_forms[df_forms["is_default"] == 0].merge(
            df_pokemon[["id", "species_id"]],
            left_on="pokemon_id",
            right_on="id",
            how="left",
            suffixes=("", "_poke"),
        ).merge(
            df_vg[["id", "generation_id"]],
            left_on="introduced_in_version_group_id",
            right_on="id",
            how="left",
            suffixes=("", "_vg"),
        )
        df_forms_processed = (
            df_forms_non_default[["id", "pokemon_id", "species_id", "identifier", "form_identifier", "generation_id"]]
            .assign(has_gender_differences=0)
            .rename(columns={"id": "form_id", "generation_id": "generation"})
            .sort_values(by=["pokemon_id", "form_id"])
        )
        form_entries = df_forms_processed.to_dict("records")

    # 2. Determine target categories
    target_categories = {}
    if category.lower() == "all":
        target_categories = CATEGORIES
    elif category.lower() in CATEGORIES:
        target_categories = {category.lower(): CATEGORIES[category.lower()]}
    else:
        print(f"[ERROR] Invalid category '{category}'. Available: {list(CATEGORIES.keys())} or 'all'")
        return

    all_grouped_issues = []
    stats_by_category = {}
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
            "affected_entries": len(cat_issues),
        }
        print(f"  Result: {len(cat_issues)} affected entries ({flawed_targets:,} flawed files) out of {cat_targets:,} asset targets.")

    # 4. Save Grouped CSV Report
    if not no_csv:
        csv_file = Path(csv_out) if csv_out else (SCRIPT_DIR / "sprite_audit_report.csv")
        if all_grouped_issues:
            csv_rows = []
            for item in all_grouped_issues:
                csv_rows.append(
                    {
                        "category": item["category"],
                        "category_name": item["category_name"],
                        "pokemon_id": item["pokemon_id"],
                        "form_id": item["form_id"],
                        "identifier": item["identifier"],
                        "species_id": item["species_id"],
                        "generation": item["generation"],
                        "is_form": item["is_form"],
                        "has_gender_differences": item["has_gender_differences"],
                        "missing_sprites": item["missing_str"],
                        "wrong_size_sprites": item["wrong_size_str"],
                        "corrupt_sprites": item["corrupt_str"],
                        "issue_summary": item["issue_summary"],
                    }
                )
            df_report = pd.DataFrame(csv_rows).sort_values(
                by=["category", "generation", "pokemon_id"],
                ascending=[True, True, True],
            )
            df_report.to_csv(csv_file, index=False)
            print(f"\n[REPORT] CSV Report saved to: {csv_file}")
        else:
            pd.DataFrame(
                columns=[
                    "category",
                    "category_name",
                    "pokemon_id",
                    "form_id",
                    "identifier",
                    "species_id",
                    "generation",
                    "is_form",
                    "has_gender_differences",
                    "missing_sprites",
                    "wrong_size_sprites",
                    "corrupt_sprites",
                    "issue_summary",
                ]
            ).to_csv(csv_file, index=False)
            print(f"\n[OK] Zero issues found! CSV report saved to: {csv_file}")

    # 5. Save HTML Dashboard
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
    )

    # If writing to website folder, also export structured JSON and CSV for direct site downloads
    if html_target.parent == WEBSITE_DIR:
        website_json = WEBSITE_DIR / "audit_data.json"
        website_csv = WEBSITE_DIR / "audit_report.csv"
        website_payload = {
            "total_asset_targets": grand_total_targets,
            "total_passed_assets": grand_total_passed,
            "total_missing_assets": grand_total_missing,
            "total_wrong_size_assets": grand_total_wrong_size,
            "total_corrupt_assets": grand_total_corrupt,
            "stats_by_category": stats_by_category,
            "affected_entries": all_grouped_issues,
        }
        with open(website_json, "w", encoding="utf-8") as f:
            json.dump(website_payload, f, indent=2)
        if not no_csv and csv_file.exists():
            import shutil
            shutil.copyfile(csv_file, website_csv)

    # 6. Console Summary
    print("\n" + "=" * 60)
    print("OVERALL AUDIT SUMMARY")
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
    print("=" * 60 + "\n")


def parse_args_and_run():
    parser = argparse.ArgumentParser(description="Audit Pokémon Sprites across categories and formats")
    parser.add_argument(
        "--category",
        choices=["default", "official-artwork", "home", "showdown", "dream-world", "all"],
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
        help="Attempt to repair corrupt images by re-saving via Pillow",
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

    args = parser.parse_args()
    check_assets(
        category=args.category,
        include_forms=args.include_forms,
        repair_enabled=args.repair,
        html_out=args.html,
        csv_out=args.csv,
        no_csv=args.no_csv,
    )


if __name__ == "__main__":
    parse_args_and_run()