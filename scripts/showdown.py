import difflib
import pathlib
import typing as t

import requests
import tabulate
from bs4 import BeautifulSoup

# NOTE: Doesn't account for females, refer this and manually check them in later https://bulbapedia.bulbagarden.net/wiki/List_of_Pok%C3%A9mon_with_gender_differences

DRY_RUN = False
SHOWDOWN_DIR = pathlib.Path(__file__).parent.parent / "sprites" / "pokemon" / "other" / "showdown"
SHOWDOWN_BASE_URL = "https://play.pokemonshowdown.com/sprites/ani"


class PokemonRecord(t.TypedDict):
    id: int
    name: str


def list_pokemon() -> dict[str, str]:
    """Retrieve a list of all Pokémon from the PokéAPI.
    The result is a mapping of Pokémon IDs to their names.

    **MAIN PROBLEM**: naming scheme for alt forms is different between Showdown and PokéAPI
    """
    api_url = "https://pokeapi.co/api/v2/pokemon?limit=10000" # MAIN PROBLEM : naming scheme for alt forms is different between Showdown and PokéAPI
    response = requests.get(api_url)

    if response.status_code != 200:
        raise Exception(f"Failed to retrieve Pokémon list (Status {response.status_code})")

    data = response.json()
    return {i["url"].split("/")[-2]: i["name"] for i in data["results"]} # names in here are NOT the same as Showdown's naming scheme - matching FAILS sometimes


def list_showdown_images(folder: pathlib.Path) -> set[str]:
    """List all Pokémon images available in the local directory."""
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
    if "-" in name:
        return tuple(name.split("-", 1))
    return name, ""


def normalize_showdown_name(showdown_name: str, known_names: set[str]) -> str:
    """Map a Showdown sprite name to the most likely PokéAPI species name."""
    # exact match
    if showdown_name in known_names:
        return showdown_name
    base, _ = resolve_alt_form_name(showdown_name)
    if base in known_names:
        return base
    # try fuzzy matches on full and base name
    match = difflib.get_close_matches(showdown_name, list(known_names), n=1, cutoff=0.8)
    if match:
        return match[0]
    match = difflib.get_close_matches(base, list(known_names), n=1, cutoff=0.8)
    if match:
        return match[0]
    return showdown_name


def build_showdown_to_species_map(showdown_index: set[str], name_to_id: dict[str, str]) -> dict[str, str]:
    names_set = set(name_to_id.keys())
    return {sname: normalize_showdown_name(sname, names_set) for sname in showdown_index}


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
        # mappa remote_name -> normalized_pokeapi_name
        remote_to_species = build_showdown_to_species_map(showdown_index, name_to_id)

        print(f"\n{'=' * 40}\nMissing images in folder: {folder}\n{'=' * 40}\n")

        remaining: set[str] = set()

        for pid, name in pokemon_list.items():

            # cerca remote entries che corrispondono alla specie PokeAPI
            candidates = [remote for remote, species in remote_to_species.items() if species == name]

            if candidates:
                # Se c'è una sola candidate la usiamo direttamente; se ce ne sono più richiedi scelta.
                if len(candidates) == 1:
                    chosen = candidates[0]
                else:
                    print(f"Multiple Showdown sprites found for {name} (ID={pid}):")
                    for i, cand in enumerate(candidates, start=1):
                        print(f"  {i}) {cand}")
                    chosen = None
                    while True:
                        answer = input("     [N/number]: ").strip().lower()
                        if answer in ("n", "no"):
                            remaining.add(pid)
                            break
                        if answer.isdigit():
                            idx = int(answer) - 1
                            if 0 <= idx < len(candidates):
                                chosen = candidates[idx]
                                print(f"     Selected {chosen} for {name}\n")
                                break
                        print("     Invalid choice; enter N or a number corresponding to one of the options.")
                if chosen:
                    save_id = resolve_save_id(pid, chosen, name_to_id)
                    save_name = f"{name}" if "-" not in chosen else f"{name}"
                    if not DRY_RUN:
                        download_image(
                            f"{save_id}{'-' + chosen.split('-', 1)[1] if '-' in chosen else ''}",
                            chosen,
                            folder,
                            f"{_construct_showdown_url(back=back, shiny=shiny)}/{chosen}.gif",
                        )
            else:
                # nessuna corrispondenza trovata tra i nomi Showdown e la specie
                print(f"No Showdown sprite found for {name} (ID={pid})")
                base_form = name.split("-", 1)
                base_form_name = base_form[0]
                base_candidates = [remote for remote, species in remote_to_species.items() if species == base_form_name]
                if base_candidates:
                    print(f"  -> but found base form sprite(s): {', '.join(base_candidates)}\n")
                    # Se c'è una sola candidate: richiesta Y/N. Se multiple: richiedi N o un numero per selezionare.
                    if len(base_candidates) == 1:
                        print(f"     Is this acceptable for alt form '{name}'? (Y/N)")
                        answer = input("     [y/N]: ").strip().lower()
                        if answer in ("y", "yes", ""):
                            chosen = base_candidates[0]
                            print(f"     Accepted alternate form '{name.split('-', 1)[1]}' for '{base_form_name}'\n")
                        else:
                            remaining.add(pid)
                            continue
                    else:
                        print(f"     Choose one of the following options or enter N to skip:")
                        for i, cand in enumerate(base_candidates, start=1):
                            print(f"       {i}) {cand}")
                        chosen = None
                        while True:
                            answer = input("     [N/number]: ").strip().lower()
                            if answer in ("n", "no"):
                                remaining.add(pid)
                                break
                            if answer.isdigit():
                                idx = int(answer) - 1
                                if 0 <= idx < len(base_candidates):
                                    chosen = base_candidates[idx]
                                    print(f"     Accepted alternate form '{name.split('-', 1)[1]}' for '{base_form_name}'\n")
                                    break
                            print("     Invalid choice; enter N or a number corresponding to one of the options.")
                    if chosen:
                        save_id = resolve_save_id(pid, chosen, name_to_id)
                        if not DRY_RUN:
                            download_image(
                                save_id,
                                chosen,
                                folder,
                                f"{_construct_showdown_url(back=back, shiny=shiny)}/{chosen}.gif",
                            )
                else:
                    remaining.add(pid)

        print(f"\nSummary for folder: {folder}\n{'-' * 40}\n")
        table = tabulate.tabulate(
            [(pid, pname) for pid, pname in pokemon_list.items() if pid in (missing_images if DRY_RUN else remaining)],
            headers=["Pokémon ID", "Pokémon Name"],
            tablefmt="github",
        )

        print(table)
