import requests
import re
from pathlib import Path

# Image URLs collected from the Smogon Sprite Project spreadsheet
# (spreadsheet link is provided inside the Smogon thread below).
# These links point to attachment files hosted on Smogon forums.
# Smogon thread:
# https://www.smogon.com/forums/threads/smogon-sprite-project.3647722/
urls = [
    "https://www.smogon.com/forums/attachments/964-png.603593/",
    "https://www.smogon.com/forums/attachments/964s-png.603594/",
    # "https://www.smogon.com/forums/attachments/964-png.536964/",
    # "https://www.smogon.com/forums/attachments/964s-png.536965/",
]

# Set a User-Agent to prevent Smogon from blocking the request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.31"
}


def download_sprites():
    script_dir = Path(__file__).resolve().parent
    download_dir = script_dir / "downloads"
    download_dir.mkdir(exist_ok=True)

    print(f"📁 Directory ready: {download_dir.absolute()}")
    print(f"🚀 Starting download of {len(urls)} files...")

    for url in urls:
        try:
            # 1. Extract filename from URL
            # Example: 652sb-png.492504/ -> 652sb.png
            match = re.search(r"attachments/([\w-]+)-png\.\d+/?", url)
            if match:
                filename = f"{match.group(1)}.png"
            else:
                # Fallback if regex fails
                filename = f"{Path(url).parts[-1].split('-')[0]}.png"

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
