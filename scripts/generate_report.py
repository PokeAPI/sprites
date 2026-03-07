# python .\generate_report.py --local-path "../sprites/pokemon/versions" --output .\out\report.html

import os
import argparse
import logging
from datetime import datetime
from typing import Dict, Set, Tuple, List

import requests
import requests_cache
import natsort


# ---------------------------------------------------------------------------
# Setup caching (24h)
# ---------------------------------------------------------------------------
requests_cache.install_cache(
    "api_cache", backend="sqlite", use_cache_dir=True, expire_after=86400
)


# ---------------------------------------------------------------------------
# Static folder config, extend this map to test more generations/games/folders
# ---------------------------------------------------------------------------
FOLDER: Dict[str, List[str]] = {
    "generation-viii": ["brilliant-diamond-shining-pearl"],
    "generation-ix": ["scarlet-violet"],
}


# Typing
FileInfo = Dict[str, Tuple[str, str, Set[str]]]


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API helper functions
# ---------------------------------------------------------------------------
def get_pokemon_data(api_url: str, endpoint: str, identifier: str) -> dict:
    """Request PokéAPI data for a specific endpoint."""
    url = f"{api_url}/{endpoint}/{identifier}"
    response = requests.get(url)

    if response.status_code != 200:
        logger.warning(f"API request failed: {url} (Status {response.status_code})")
        return {}

    return response.json()


# ---------------------------------------------------------------------------
# Local filesystem scan
# ---------------------------------------------------------------------------
def get_local_images(local_path: str, folder_config: Dict[str, List[str]]) -> FileInfo:
    """Scan local directories for image files."""
    all_files_by_path: FileInfo = {}

    for gen_key, games in folder_config.items():
        for game_key in games:
            path = os.path.join(local_path, gen_key, game_key)

            try:
                files = {
                    f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))
                }

                logger.info(f"Found {len(files)} files in '{path}'.")
                all_files_by_path[path] = (gen_key, game_key, files)

            except FileNotFoundError:
                logger.warning(f"Local path '{path}' not found. Skipping.")
                all_files_by_path[path] = (gen_key, game_key, set())

    return all_files_by_path


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------
def create_table(
    path_prefix: str,
    generation_key: str,
    game_key: str,
    file_set: Set[str],
    api_url: str,
) -> str:
    """Generate the HTML table displaying comparison images."""
    table_rows = ""

    for filename in natsort.natsorted(file_set):
        identifier = os.path.splitext(filename)[0]
        base_id = identifier.split("-", 1)[0]

        is_variant = "-" in identifier
        variant_suffix = identifier.split("-", 1)[1] if is_variant else ""

        logger.info(f"Processing '{filename}'")

        final_api_identifier = base_id
        error = False
        found_variant_match = False

        # Variant handling
        if is_variant:
            species_data = get_pokemon_data(api_url, "pokemon-species", base_id)

            if species_data:
                for variety in species_data.get("varieties", []):
                    api_name = variety.get("pokemon", {}).get("name", "")

                    if api_name.endswith(f"-{variant_suffix}"):
                        final_api_identifier = api_name
                        found_variant_match = True
                        error = False
                        break
                    else:
                        error = True
            else:
                error = True

        # Base Pokémon fetch
        pokemon = get_pokemon_data(api_url, "pokemon", final_api_identifier)
        pokemon_sprites = pokemon.get("sprites") if pokemon else None

        # Form fallback
        if is_variant and not found_variant_match and pokemon:
            for form in pokemon.get("forms", []):
                form_name = form.get("name", "")
                if form_name.endswith(f"-{variant_suffix}"):
                    form_data = get_pokemon_data(api_url, "pokemon-form", form_name)
                    pokemon_sprites = form_data.get("sprites", {})
                    error = False
                    break

        # Extract sprites
        default_sprite = (
            pokemon_sprites.get("front_default", "") if pokemon_sprites else ""
        )

        version_sprite = (
            pokemon_sprites.get("versions", {})
            .get(generation_key, {})
            .get(game_key, {})
            .get("front_default", "")
            if pokemon_sprites
            else ""
        )

        # Add HTML row
        table_rows += f"""
            <div class="inline-flex flex-col items-center m-1 p-2 border-2 {"bg-red-600" if error else "border-indigo-600"}">
                <span class="text-xs text-gray-500">{identifier}</span>
                <img src="{default_sprite}" style="max-width: 96px; object-fit: contain;">
                <img src="{version_sprite}" style="max-width: 96px; object-fit: contain;">
            </div>
        """

    return f"""
        <h2 class="text-xl font-bold mt-6 mb-3 border-b-2 pb-1">
            Analysis for path: <code>{path_prefix}</code> ({len(file_set)} files)
        </h2>
        <div class="flex flex-wrap">
            {table_rows}
        </div>
    """


# ---------------------------------------------------------------------------
# Full report generation
# ---------------------------------------------------------------------------
def generate_report(
    local_path: str, api_url: str, output_file: str, cli_args: dict
) -> None:
    """Generate the entire HTML report."""
    all_files_by_path = get_local_images(local_path, FOLDER)

    tables_html = ""
    for path, (gen_key, game_key, files) in all_files_by_path.items():
        if files:
            tables_html += create_table(path, gen_key, game_key, files, api_url)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Render CLI args as HTML
    cli_args_html = (
        "<ul>"
        + "".join(f"<li><strong>{k}</strong>: {v}</li>" for k, v in cli_args.items())
        + "</ul>"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sprites Report</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="p-6 bg-gray-100">
        <h1 class="text-3xl font-bold mb-4">Sprites Report</h1>
        <p><strong>Generated on:</strong> {timestamp}</p>
        <h2 class="text-xl font-bold mt-2 mb-2">CLI Arguments:</h2>
        {cli_args_html}

        {tables_html}
    </body>
    </html>
    """

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Report successfully created: {os.path.abspath(output_file)}")


# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate Pokémon sprite comparison report."
    )

    parser.add_argument(
        "--local-path",
        required=True,
        help="Base directory containing the local sprite folders.",
    )

    parser.add_argument(
        "--api-url",
        help="Base URL of the Pokémon API.",
        default="http://localhost/api/v2",
    )

    parser.add_argument(
        "--output", required=True, help="Path to the generated HTML report."
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear requests_cache before execution.",
        default=False,
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.clear_cache:
        requests_cache.clear()
        logger.info("Cache cleared before run.")

    generate_report(
        local_path=args.local_path,
        api_url=args.api_url,
        output_file=args.output,
        cli_args=vars(args),
    )
