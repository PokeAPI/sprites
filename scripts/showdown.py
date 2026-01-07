import difflib
import pathlib
import typing as t

import requests
import tabulate
from bs4 import BeautifulSoup

# NOTE: Doesn't account for females, refer this and manually check them in later https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_with_gender_differences

DRY_RUN = True
SHOWDOWN_DIR = pathlib.Path(__file__).parent.parent / "sprites" / "pokemon" / "other" / "showdown"
SHOWDOWN_BASE_URL = "https://play.pokemonshowdown.com/sprites/ani"


class PokemonRecord(t.TypedDict):
    id: int
    name: str


def list_pokemon() -> dict[str, str]:
    """Retrieve a list of all Pokémon from the PokéAPI."""
    api_url = "https://pokeapi.co/api/v2/pokemon?limit=10000" # MAIN PROBLEM : naming scheme for alt forms is different between Showdown and PokéAPI
    response = requests.get(api_url)

    if response.status_code != 200:
        raise Exception(f"Failed to retrieve Pokémon list (Status {response.status_code})")

    data = response.json()
    return {i["url"].split("/")[-2]: i["name"] for i in data["results"]} # names in here are NOT the same as Showdown's naming scheme - matching FAILS sometimes


def list_showdown_images(folder: pathlib.Path) -> set[str]:
    """List all Pokémon images available in the Showdown directory."""
    image_files = {f.stem for f in folder.glob("*.gif") if f.is_file()}
    return image_files


def _construct_showdown_url(back: bool = False, shiny: bool = False) -> str:
    """Construct the Showdown URL based on image type."""
    base_url = SHOWDOWN_BASE_URL
    if back:
        base_url += "-back"
    if shiny:
        base_url += "-shiny"
    return base_url


def showdown_sprite_index(back: bool = False, shiny: bool = False) -> set[str]:
    """Retrieve the index of available Pokémon sprites from Showdown."""
    index = requests.get(_construct_showdown_url(back, shiny))
    if index.status_code != 200:
        raise Exception(f"Failed to retrieve Showdown sprite index (Status {index.status_code})")
    soup = BeautifulSoup(index.text, "html.parser")
    links = soup.find_all("a")
    return {
        str(link.get("href")).strip("./").split(".")[0] for link in links if str(link.get("href", "")).endswith(".gif")
    }


def download_image(id: str, name: str, folder: pathlib.Path, pokemon_url: str) -> None:
    """Download a Pokémon image from the Showdown repository."""
    response = requests.get(pokemon_url)
    if response.status_code != 200:
        print(f"Failed to download image for {name} (Status {response.status_code})")
        return

    with open(folder / f"{id}.gif", "wb") as img_file:
        img_file.write(response.content)

    print(f"Downloaded image for {name} to {folder / f'{id}.gif'}")

def resolve_alt_form_name(name: str) -> tuple[str, str]:
    """Return the base form name and the alt form suffix from a Showdown image name."""
    return name.split("-", 1)

def resolve_save_id(pid: str, sprite_name: str, name_to_id: dict[str, str]) -> str:
    """Return the id string to use when saving the sprite file.
    If pid refers to an alternate-form placeholder (>10000), map to the base form id when available."""
    try:
        pid_int = int(pid)
    except ValueError:
        return pid
    if pid_int > 10000:
        base_name, _ = resolve_alt_form_name(sprite_name)
        return name_to_id.get(base_name, pid)
    return pid


if __name__ == "__main__":
    pokemon_list = list_pokemon()
    # mappa name -> id per risolvere lookup per nome
    name_to_id = {v: k for k, v in pokemon_list.items()}

    showdown_folders = (
        SHOWDOWN_DIR,
        SHOWDOWN_DIR / "shiny",
        SHOWDOWN_DIR / "back",
        SHOWDOWN_DIR / "back" / "shiny",
    )

    for folder in showdown_folders:
        showdown_images = list_showdown_images(folder)
        missing_images = set(pokemon_list.keys()) - showdown_images

        back = "back" in folder.parts
        shiny = "shiny" in folder.parts

        showdown_index = showdown_sprite_index(back=back, shiny=shiny)

        print(f"\n{'=' * 40}\nMissing images in folder: {folder}\n{'=' * 40}\n")

        remaining: set[str] = set()

        for pid, name in pokemon_list.items():
            if pid in missing_images and not DRY_RUN:
                if name in showdown_index:
                    download_image(
                        resolve_save_id(pid, name, name_to_id),
                        name,
                        folder,
                        f"{_construct_showdown_url(back=back, shiny=shiny)}/{name}.gif",
                    )
            else:

                print(f"\nDownloading image for {name} (ID = {pid})")
                base_form_id = resolve_save_id(pid, name, name_to_id)
                base_form_name = resolve_alt_form_name(name)
                base_form = pokemon_list.get(base_form_id)
                print(f"Exact name not found in Showdown index: {name} - Possible alternate form")
                if base_form != name and base_form in showdown_index:
                    print(f"Found base form in Showdown index: {base_form} (ID = {base_form_id}), name of downloaded image will be modified.")
                    # downloading current image, but saving it under "<base_form_id>/<alternate_form>"
                    if not DRY_RUN:
                        download_image(
                            f"{base_form_id}-{base_form_name[1]}",
                            f"{base_form_name[0]}-{base_form_name[1]}",
                            folder,
                            f"{_construct_showdown_url(back=back, shiny=shiny)}/{name}.gif",
                        )
                else:
                    print(f"No suitable alternate form found for {name}. Skipping.")
                    remaining.add(pid)
                        
        table = tabulate.tabulate(
            [(pid, pname) for pid, pname in pokemon_list.items() if pid in (missing_images if DRY_RUN else remaining)],
            headers=["Pokémon ID", "Pokémon Name"],
            tablefmt="github",
        )

        print(table)
