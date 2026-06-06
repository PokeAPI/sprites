import argparse
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
from PIL import Image, ImageFile

# CONFIGURATION
GITHUB_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
POKEMON_CSV_URL = f"{GITHUB_BASE_URL}/pokemon.csv"
FORMS_CSV_URL = f"{GITHUB_BASE_URL}/pokemon_forms.csv"
VG_CSV_URL = f"{GITHUB_BASE_URL}/version_groups.csv"

# Local Sprite directories relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_PATH = SCRIPT_DIR.parent / "sprites" / "pokemon"

PATHS = {
    "Front": BASE_PATH,
    "Front Shiny": BASE_PATH / "shiny",
    "Back": BASE_PATH / "back",
    "Back Shiny": BASE_PATH / "back" / "shiny",
}


def get_standard_dimension():
    """Scans all folders to find the most common image size (The Standard)."""
    print("📏 Determining standard image dimensions...")
    all_sizes = []
    valid_ext = (".png", ".jpg", ".jpeg")

    for folder in PATHS.values():
        if not folder.exists():
            continue
        for file in sorted(folder.glob("*")):
            if file.suffix.lower() in valid_ext:
                try:
                    with Image.open(file) as img:
                        all_sizes.append(img.size)
                except Exception:
                    continue

    if not all_sizes:
        return None

    most_common = Counter(all_sizes).most_common(1)[0][0]
    print(f"🎯 Standard identified as: {most_common[0]}x{most_common[1]}")
    return most_common


def scan_entries(pokemon_entries, standard_size, collect_corrupts: bool = False):
    """Scan entries, return (report_list, corrupt_set).

    If collect_corrupts=True unreadable files are added to corrupt_set for a later repair pass.
    """
    report = []
    corrupt_paths = set()

    for pokemon in pokemon_entries:
        p_id = pokemon["pokemon_id"]
        s_id = pokemon["species_id"]
        name = pokemon["identifier"]
        gen = int(pokemon["generation"]) if pd.notnull(pokemon["generation"]) else "Unknown"
        filename = f"{p_id}.png"

        for label, folder in PATHS.items():
            file_path = folder / filename
            issue = None

            if not file_path.exists():
                issue = "missing_file"
            else:
                try:
                    with Image.open(file_path) as img:
                        if img.size != standard_size:
                            issue = f"wrong_size_{img.size[0]}x{img.size[1]}"
                except Exception as e:
                    print(f"⚠️ Error opening {file_path}: {e}")
                    if collect_corrupts:
                        corrupt_paths.add(file_path)
                    issue = "corrupt_file"

            if issue:
                report.append(
                    {
                        "pokemon_id": p_id,
                        "identifier": name,
                        "species_id": s_id,
                        "sprite_type": label.lower().replace(" ", "_"),
                        "generation": gen,
                        "issue": issue,
                    }
                )

    return report, corrupt_paths


def attempt_repair(path: Path) -> bool:
    """Try to repair an unreadable image by loading with truncated-images enabled and re-saving.

    Returns True if the file was replaced with a re-saved copy, False otherwise.
    """
    try:
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        with Image.open(path) as im:
            im.load()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
                tmpname = tf.name
            im.save(tmpname, format="PNG")
            shutil.move(tmpname, str(path))
        return True
    except Exception as ex:
        print(f"  repair failed: {ex}")
        try:
            if "tmpname" in locals() and Path(tmpname).exists():
                Path(tmpname).unlink()
        except Exception:
            pass
        return False


def check_assets(repair_enabled: bool = False):
    print("\n" + "=" * 50)
    print("🔍 POKÉMON SPRITE AUDIT")
    print(f"📂 Script: {Path(__file__).name}")
    print("=" * 50 + "\n")

    # 1. Establish the Baseline
    standard_size = get_standard_dimension()
    if not standard_size:
        print("❌ No images found to establish a standard size.")
        return

    # 2. Load Data from GitHub
    print("🌐 Fetching latest Pokémon data from GitHub...")
    try:
        df_pokemon = pd.read_csv(POKEMON_CSV_URL)
        df_forms = pd.read_csv(FORMS_CSV_URL)
        df_vg = pd.read_csv(VG_CSV_URL)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return

    # 3. Process Data
    df_forms_subset = df_forms[df_forms["is_default"] == 1][
        ["pokemon_id", "introduced_in_version_group_id"]
    ]

    df_merged = df_pokemon.merge(
        df_forms_subset, left_on="id", right_on="pokemon_id", how="left"
    )
    df_merged = df_merged.merge(
        df_vg[["id", "generation_id"]],
        left_on="introduced_in_version_group_id",
        right_on="id",
        how="left",
    )

    df_entries = (
        df_merged[["id_x", "species_id", "identifier", "generation_id"]]
        .rename(columns={"id_x": "pokemon_id", "generation_id": "generation"})
    )

    # Ensure deterministic ordering by pokemon_id
    df_entries = df_entries.sort_values(by=["pokemon_id"])
    pokemon_entries = df_entries.to_dict("records")

    # 4. Deep Scan (Existence + Dimensions)
    print(f"🧪 Scanning {len(pokemon_entries)} entries across {len(PATHS)} categories...")

    # First pass: collect corrupt files (if any)
    report_data, corrupt_set = scan_entries(pokemon_entries, standard_size, collect_corrupts=True)

    if repair_enabled and corrupt_set:
        print(f"\nFound {len(corrupt_set)} corrupt/unopenable files; attempting repair...")
        for path in sorted(corrupt_set):
            print(f"  → Repairing {path}...")
            success = attempt_repair(path)
            print(f"    {'success' if success else 'failed'}: {path}")

        # Re-scan after repair attempts
        report_data, _ = scan_entries(pokemon_entries, standard_size, collect_corrupts=False)

    # 5. Output Report & Preview
    if report_data:
        df_report = pd.DataFrame(report_data).sort_values(
            by=["generation", "sprite_type", "pokemon_id"], ascending=[True, True, True]
        )
        report_name = f"{Path(__file__).stem}_report.csv"
        output_path = SCRIPT_DIR / report_name
        df_report.to_csv(output_path, index=False)

        print("\n" + "=" * 50)
        print("📊 AUDIT SUMMARY")
        print("=" * 50)

        # Show totals for each issue type
        summary = df_report["issue"].value_counts()
        for issue_type, count in summary.items():
            print(f"{issue_type:.<30} {count:>5}")

        print("-" * 50)
        print(f"✅ Total Issues Found: {len(df_report)}")
        print(f"📂 Report saved to: {report_name}")
        print("=" * 50)
    else:
        print("\n✨ Audit complete: 0 issues found. Your sprite collection is perfect!")


def parse_args_and_run():
    parser = argparse.ArgumentParser(description="Audit Pokémon sprites")
    parser.add_argument("--repair", action="store_true", help="Attempt to repair corrupt images by re-saving via Pillow")
    args = parser.parse_args()
    check_assets(repair_enabled=args.repair)


if __name__ == "__main__":
    parse_args_and_run()