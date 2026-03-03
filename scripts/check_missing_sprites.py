import pandas as pd
from pathlib import Path

# CONFIGURATION
GITHUB_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
POKEMON_CSV_URL = f"{GITHUB_BASE_URL}/pokemon.csv"
FORMS_CSV_URL = f"{GITHUB_BASE_URL}/pokemon_forms.csv"
VG_CSV_URL = f"{GITHUB_BASE_URL}/version_groups.csv"

# Local Sprite directories relative to this script
# .parent.parent refers to /Parent/ (going up from /Parent/sprites/scripts/)
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_PATH = SCRIPT_DIR.parent / "sprites" / "pokemon"

PATHS = {
    "Front": BASE_PATH,
    "Front Shiny": BASE_PATH / "shiny",
    "Back": BASE_PATH / "back",
    "Back Shiny": BASE_PATH / "back" / "shiny",
}


def check_sprites():
    # 1. Load Data from GitHub
    print("🌐 Fetching latest Pokémon data from GitHub...")
    try:
        df_pokemon = pd.read_csv(POKEMON_CSV_URL)
        df_forms = pd.read_csv(FORMS_CSV_URL)
        df_vg = pd.read_csv(VG_CSV_URL)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return

    # 2. Merge Data
    print("🔍 Processing data and identifying versions...")

    # Get generation info via forms
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

    pokemon_entries = (
        df_merged[["id_x", "species_id", "identifier", "generation_id"]]
        .rename(columns={"id_x": "pokemon_id", "generation_id": "generation"})
        .to_dict("records")
    )

    # 3. Check Local Files
    print(f"🧪 Scanning local folders for {len(pokemon_entries)} Pokémon...")

    all_missing = []

    for pokemon in pokemon_entries:
        p_id = pokemon["pokemon_id"]
        s_id = pokemon["species_id"]
        name = pokemon["identifier"]
        gen = (
            int(pokemon["generation"])
            if pd.notnull(pokemon["generation"])
            else "Unknown"
        )
        filename = f"{p_id}.png"

        for label, folder in PATHS.items():
            file_path = folder / filename

            if not file_path.exists():
                all_missing.append(
                    {
                        "pokemon_id": p_id,
                        "identifier": name,
                        "species_id": s_id,
                        "sprite_type": label.lower().replace(" ", "_"),
                        "generation": gen,
                    }
                )

    # 4. Save and Report
    if all_missing:
        df_missing = pd.DataFrame(all_missing)
        df_missing = df_missing.sort_values(by=["pokemon_id", "sprite_type"])

        output_path = SCRIPT_DIR / "missing_sprites.csv"
        df_missing.to_csv(output_path, index=False)

        print("\n" + "=" * 50)
        print(f"✅ REPORT GENERATED: {output_path.name}")
        print(f"❌ Total Missing Assets: {len(df_missing)}")
        print("=" * 50)
        print(df_missing.head(10).to_string(index=False))
        if len(df_missing) > 10:
            print(f"... and {len(df_missing) - 10} more.")
    else:
        print("\n✅ All assets present! Your collection is complete.")


if __name__ == "__main__":
    check_sprites()
