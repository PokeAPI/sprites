import os
import pandas as pd

# CONFIGURATION
# Script is in: /Parent/sprites/scripts/
# Data is in:   /Parent/pokeapi/data/v2/csv/
POKEMON_CSV = "../../pokeapi/data/v2/csv/pokemon.csv"
FORMS_CSV = "../../pokeapi/data/v2/csv/pokemon_forms.csv"
VG_CSV = "../../pokeapi/data/v2/csv/version_groups.csv"

# Sprite directories relative to this script
BASE_PATH = "../sprites/pokemon"
PATHS = {
    "Front": BASE_PATH,
    "Front Shiny": os.path.join(BASE_PATH, "shiny"),
    "Back": os.path.join(BASE_PATH, "back"),
    "Back Shiny": os.path.join(BASE_PATH, "back/shiny"),
}


def check_sprites():
    # 1. Validate required files
    for f in [POKEMON_CSV, FORMS_CSV, VG_CSV]:
        if not os.path.exists(f):
            print(f"❌ Error: Missing CSV at: {os.path.abspath(f)}")
            return

    # 2. Load and Merge Data
    print("🔍 Loading Pokémon data...")
    df_pokemon = pd.read_csv(POKEMON_CSV)
    df_forms = pd.read_csv(FORMS_CSV)
    df_vg = pd.read_csv(VG_CSV)

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
        .rename(columns={"id_x": "id"})
        .to_dict("records")
    )

    # 3. Check Local Files
    print(
        f"🧪 Scanning {len(pokemon_entries)} entries across {len(PATHS)} categories..."
    )

    all_missing = []

    for pokemon in pokemon_entries:
        p_id = pokemon["id"]
        s_id = pokemon["species_id"]
        name = pokemon["identifier"]
        gen = (
            int(pokemon["generation_id"])
            if pd.notnull(pokemon["generation_id"])
            else "Unknown"
        )
        filename = f"{p_id}.png"

        for label, folder in PATHS.items():
            file_path = os.path.join(folder, filename)
            if not os.path.exists(file_path):
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

        # Sort by Pokémon ID, then by Sprite Type
        df_missing = df_missing.sort_values(by=["pokemon_id", "sprite_type"])

        output_file = "missing_sprites.csv"
        df_missing.to_csv(output_file, index=False)

        print("\n" + "=" * 50)
        print(f"✅ REPORT GENERATED: {output_file}")
        print(f"❌ Total Missing Assets: {len(df_missing)}")
        print("=" * 50)
        print(df_missing.head(10).to_string(index=False))
    else:
        print("\n✅ All assets present! No missing sprites found.")


if __name__ == "__main__":
    check_sprites()
