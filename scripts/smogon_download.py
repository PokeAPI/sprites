import requests
import re
import json
from pathlib import Path

# Image URLs collected from the Smogon Sprite Project spreadsheet
# (spreadsheet link is provided inside the Smogon thread below).
# These links point to attachment files hosted on Smogon forums.
# Smogon thread:
# https://www.smogon.com/forums/threads/smogon-sprite-project.3647722/
urls = [
    "https://www.smogon.com/forums/attachments/019-gif.171350/",
    "https://www.smogon.com/forums/attachments/19b-gif.177101/",
    "https://www.smogon.com/forums/attachments/019s-gif.173309/",
    "https://www.smogon.com/forums/attachments/19sb-gif.177103/",
]

# Set a User-Agent to prevent Smogon from blocking the request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.31"
}

# Mapping Showdown directories to filename suffixes
SHOWDOWN_SUFFIX_MAP = {
    "gen5ani": "",
    "gen5ani-back": "b",
    "gen5ani-shiny": "s",
    "gen5ani-back-shiny": "sb",
}


def load_forms_map(script_dir):
    """Loads forms.json and inverts it to {name: id} for easy lookup."""
    forms_path = script_dir / "forms.json"
    if not forms_path.exists():
        print("⚠️ Warning: forms.json not found. Showdown downloads may fail.")
        return {}

    with open(forms_path, "r") as f:
        data = json.load(f)
        # Invert {"764": "comfey"} -> {"comfey": "764"}
        return {v.lower(): k for k, v in data.items()}


def download_sprites():
    script_dir = Path(__file__).resolve().parent
    download_dir = script_dir / "downloads"
    download_dir.mkdir(exist_ok=True)

    name_to_id = load_forms_map(script_dir)

    print(f"📁 Directory ready: {download_dir.absolute()}")
    print(f"🚀 Starting download of {len(urls)} files...")

    for url in urls:
        try:
            filename = None

            # 1. Extract filename from URL
            # --- Pokemon Showdown ---
            if "play.pokemonshowdown.com" in url:
                # Extract the directory and the name (e.g., gen5ani-back and comfey)
                # URL pattern: .../sprites/{directory}/{name}.gif
                parts = url.rstrip("/").split("/")
                directory = parts[-2]
                name_with_ext = parts[-1]
                name = name_with_ext.split(".")[0].lower()
                extension = name_with_ext.split(".")[-1]

                pokemon_id = name_to_id.get(name)
                suffix = SHOWDOWN_SUFFIX_MAP.get(directory)

                if pokemon_id is not None and suffix is not None:
                    filename = f"{pokemon_id}{suffix}.{extension}"
                else:
                    print(f"⚠️ Could not map Showdown URL: {url}")
                    continue

            # --- Smogon Forums ---
            else:
                # Capture the name and the extension type (e.g., 762-gif.369401 -> 762 and gif)
                match = re.search(r"attachments/([\w-]+)-(png|gif)\.\d+/?", url)
                if match:
                    base_name = match.group(1)
                    extension = match.group(2)
                    filename = f"{base_name}.{extension}"
                else:
                    # Handles cases where the regex might miss a specific format
                    raw_part = Path(url).parts[-1].split(".")[0]  # e.g., "762-gif"
                    if "-" in raw_part:
                        name, ext = raw_part.rsplit("-", 1)
                        filename = f"{name}.{ext}"
                    else:
                        print(f"⚠️ Could not parse Smogon URL: {url}")
                        continue

            save_path = download_dir / filename

            # 2. Download the file
            response = requests.get(url, headers=HEADERS, stream=True)

            if response.status_code == 200:
                with save_path.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ Downloaded: {filename}")
            else:
                print(f"❌ Failed: {url} (Status: {response.status_code})")

        except Exception as e:
            print(f"⚠️ Error downloading {url}: {e}")

    print("\n" + "=" * 30)
    print("Download process finished.")
    print(f"Files are located in: {download_dir.resolve()}")
    print("=" * 30)


if __name__ == "__main__":
    download_sprites()
