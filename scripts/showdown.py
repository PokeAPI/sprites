import difflib
import pathlib
import typing as t

import requests
import tabulate
from bs4 import BeautifulSoup

# NOTE: Doesn't account for females, refer this and manually check them in later https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_with_gender_differences

DRY_RUN = True
SHOWDOWN_DIR = (
    pathlib.Path(__file__).parent.parent / "sprites" / "pokemon" / "other" / "showdown"
)
SHOWDOWN_BASE_URL = "https://play.pokemonshowdown.com/sprites/ani"


class PokemonRecord(t.TypedDict):
    id: int
    name: str


def list_pokemon() -> dict[str, str]:
    """Retrieve a list of all Pokémon from the PokéAPI."""
    api_url = "https://pokeapi.co/api/v2/pokemon?limit=10000"
    response = requests.get(api_url)

    if response.status_code != 200:
        raise Exception(
            f"Failed to retrieve Pokémon list (Status {response.status_code})"
        )

    data = response.json()
    return {i["url"].split("/")[-2]: i["name"] for i in data["results"]}


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
        raise Exception(
            f"Failed to retrieve Showdown sprite index (Status {index.status_code})"
        )
    soup = BeautifulSoup(index.text, "html.parser")
    links = soup.find_all("a")
    return {
        str(link.get("href")).strip("./").split(".")[0]
        for link in links
        if str(link.get("href", "")).endswith(".gif")
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


if __name__ == "__main__":
    pokemon_list = list_pokemon()

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
                        pid,
                        name,
                        folder,
                        f"{_construct_showdown_url(back=back, shiny=shiny)}/{name}.gif",
                    )
                else:
                    print(f"Exact name not found in Showdown index: {name}")
                    closest_matches = difflib.get_close_matches(
                        name, showdown_index, n=3, cutoff=0.7
                    )
                    if closest_matches:
                        print(
                            "\n".join(
                                [
                                    str(n) + ") " + m
                                    for n, m in enumerate(closest_matches, start=1)
                                ]
                            )
                        )
                        print(
                            "Enter to skip downloading this image, or enter the number of the closest match to download that image."
                        )
                        user_input = input("Your choice: ").strip()
                        try:
                            choice = int(user_input)
                            if 1 <= choice <= len(closest_matches):
                                selected_name = closest_matches[choice - 1]
                                download_image(
                                    pid,
                                    selected_name,
                                    folder,
                                    f"{_construct_showdown_url(back=back, shiny=shiny)}/{selected_name}.gif",
                                )
                            else:
                                print("Invalid choice. Skipping download.")
                                remaining.add(pid)
                        except ValueError:
                            print("Skipping download.")
                            remaining.add(pid)

        table = tabulate.tabulate(
            [
                (pid, pname)
                for pid, pname in pokemon_list.items()
                if pid in (missing_images if DRY_RUN else remaining)
            ],
            headers=["Pokémon ID", "Pokémon Name"],
            tablefmt="github",
        )

        print(table)
