import requests
import time
import argparse
from pathlib import Path

# Configuration
API_BASE_URL = "https://pokeapi.co/api/v2/pokemon-species/"

# Simple in-memory cache to store API responses
# Format: { "877": { ...api_data... } }
species_cache = {}


def get_species_data(pokedex_num):
    """Fetches data from API or returns from cache if already fetched."""
    if pokedex_num in species_cache:
        return species_cache[pokedex_num]

    print(f"--> Fetching API data for Species ID: {pokedex_num}...")
    try:
        response = requests.get(f"{API_BASE_URL}{pokedex_num}")
        if response.status_code == 200:
            data = response.json()
            species_cache[pokedex_num] = data
            return data
        elif response.status_code == 429:
            print("!!! Being rate limited. Sleeping for 5 seconds...")
            time.sleep(5)
            return get_species_data(pokedex_num)
        else:
            print(f"!!! API Error {response.status_code} for ID {pokedex_num}")
            return None
    except Exception as e:
        print(f"!!! Request failed: {e}")
        return None


def process_folders(root_path):
    root_path = Path(root_path)

    if not root_path.exists():
        print(f"Error: Folder '{root_path}' not found.")
        return

    for file_path in root_path.rglob("*.png"):
        filename = file_path.name

        if "-" in filename:
            basename = file_path.stem

            # Split only ONCE to handle names like 1011-dudunsparce-three-segment
            parts = basename.split("-", 1)

            pokedex_num = parts[0]
            variety_suffix = parts[1].lower()

            species_data = get_species_data(pokedex_num)

            if species_data:
                species_name = species_data["name"]
                varieties = species_data["varieties"]

                # Target name logic: "species-variety" (e.g., "morpeko-hangry")
                target_match_name = f"{species_name}-{variety_suffix}"

                new_id = None
                for v in varieties:
                    if v["pokemon"]["name"] == target_match_name:
                        # Extract numeric ID from the PokeAPI URL
                        url_parts = v["pokemon"]["url"].strip("/").split("/")
                        new_id = url_parts[-1]
                        break

                if new_id:
                    new_filename = f"{new_id}.png"
                    new_file_path = file_path.with_name(new_filename)

                    file_path.replace(new_file_path)
                    print(f"Success: [{file_path.parent}] {filename} -> {new_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rename Pokemon variety images via PokéAPI."
    )
    parser.add_argument("folder", help="Path to the folder to process")

    args = parser.parse_args()

    process_folders(args.folder)

    print(f"\nFinished!")
