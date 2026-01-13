import difflib
import pathlib
import typing as t

import requests
import tabulate
from bs4 import BeautifulSoup

DRY_RUN = False
SHOWDOWN_DIR = pathlib.Path(__file__).parent.parent / "sprites" / "pokemon" / "other" / "showdown"
SHOWDOWN_BASE_URL = "https://play.pokemonshowdown.com/sprites/ani"

def _construct_showdown_url(back: bool = False, shiny: bool = False) -> str:
    """Construct the Showdown URL based on image type."""
    base_url = SHOWDOWN_BASE_URL
    if back:
        base_url += "-back"
    if shiny:
        base_url += "-shiny"
    return base_url


def list_showdown_names(back: bool = False, shiny: bool = False) -> dict[str, str]:
    """Retrieve the index of available Pokémon sprites from Showdown.
    
    This set of names corresponds to the available sprite files on the Showdown server.
    Includes alt-forms as separate entries.
    """
    index = requests.get(_construct_showdown_url(back, shiny))
    if index.status_code != 200:
        raise Exception(f"Failed to retrieve Showdown sprite index (Status {index.status_code})")
    soup = BeautifulSoup(index.text, "html.parser")
    links = soup.find_all("a")
    names_list = { str(link.get("href")).strip("./").split(".")[0] for link in links if str(link.get("href", "")).endswith(".gif") }
    return names_list


def list_pokeapi_names() -> dict[str, str]:
    """Retrieve a list of all Pokémon from the PokéAPI API, formatted as a dictionary mapping Pokémon IDs (entries in the National Dex) to their names.

    This list only includes Pokémon names, without any alt-form remapping.
    """
    api_url = "https://pokeapi.co/api/v2/pokemon?limit=1025"
    response = requests.get(api_url)

    if response.status_code != 200:
        raise Exception(f"Failed to retrieve Pokémon list (Status {response.status_code})")

    data = response.json()
    return {i["url"].split("/")[-2]: i["name"] for i in data["results"]}


def download_image(id: str, name: str, folder: pathlib.Path, pokemon_url: str) -> None:
    """Download a Pokémon image from the Showdown repository."""
    response = requests.get(pokemon_url)
    if response.status_code != 200:
        print(f"Failed to download image for {name} (Status {response.status_code})")
        return

    with open(folder / f"{id}.gif", "wb") as img_file:
        img_file.write(response.content)

    print(f"Downloaded image for {name} to {folder / f'{id}.gif'}")


pokeapi_list = list_pokeapi_names()
id_list = {v: k for k, v in pokeapi_list.items()}

showdown_list = list_showdown_names()

final_list = {}

showdown_folders = (
    SHOWDOWN_DIR,
    SHOWDOWN_DIR / "shiny",
    SHOWDOWN_DIR / "back",
    SHOWDOWN_DIR / "back" / "shiny",
)

for showdown_name in showdown_list:
    if showdown_name in pokeapi_list.values():
        final_list[id_list[showdown_name]] = showdown_name
    else:
        showdown_base_name = showdown_name.split("-", 1)[0]
        showdown_suffix = showdown_name.split("-", 1)[1] if "-" in showdown_name else ""
        pokeapi_base_names_list = { v: name.split("-", 1)[0] for v, name in pokeapi_list.items() }
        if showdown_base_name in pokeapi_base_names_list.values():
            pokeapi_base_ids = { k: v for v, k in pokeapi_base_names_list.items() }
            id = pokeapi_base_ids[showdown_base_name]
            final_list[f"{id}-{showdown_suffix}"] = showdown_name
        else:
            closest_matches = difflib.get_close_matches(showdown_name, pokeapi_list.values(), n=5, cutoff=0.8)
            if closest_matches:
                id = id_list[closest_matches[0]]
                final_list[f"{id}"] = showdown_name
            else:
                base_closest_matches = difflib.get_close_matches(showdown_base_name, pokeapi_base_names_list.values(), n=5, cutoff=0.8)
                if base_closest_matches:
                    id = pokeapi_base_ids[base_closest_matches[0]]
                    final_list[f"{id}-{showdown_suffix}"] = showdown_name
                else:
                    print(f"Could not find match for Showdown name: {showdown_name}")

final_list = dict(sorted(final_list.items(), key=lambda x: (int(x[0].split("-")[0]), x[0])))

for folder in showdown_folders:
    shiny = "shiny" in folder.parts
    back = "back" in folder.parts
    for (id, name) in final_list.items():
        pokemon_url = f"{_construct_showdown_url(shiny, back)}/{name}.gif"
        if not DRY_RUN:
            download_image(id, name, SHOWDOWN_DIR, pokemon_url)
        else:
            print(f"[DRY RUN] Would download image for {name} to {f'{id}.gif'} from {pokemon_url}")