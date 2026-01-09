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

    <hr>

    **MAIN PROBLEM**: naming scheme for alt forms is different between Showdown and PokéAPI

    - *Current solution*: try to map names using fuzzy matching where exact match is not found
    ️- *Possible future solution*: maintain a manual mapping file for known mismatches
    """
    api_url = "https://pokeapi.co/api/v2/pokemon?limit=10000" # MAIN PROBLEM : naming scheme for alt forms is different between Showdown and PokéAPI
    response = requests.get(api_url)

    if response.status_code != 200:
        raise Exception(f"Failed to retrieve Pokémon list (Status {response.status_code})")

    data = response.json()
    results = {i["url"].split("/")[-2]: i["name"] for i in data["results"]}
    above_10000 = {k: v for k, v in results.items() if int(k) > 10000}
    for k, v in above_10000.items():
        print(f"Found sprite ID > 10000 in PokéAPI listing: {k} -> {v}")
        print(" -> Possibly an alt form placeholder - trying to search for base form instead")
        base_form_name = v.split("-", 1)[0]
        base_form_id = next((id_ for id_, name in results.items() if name.split("-", 1)[0] == base_form_name), None)
        if base_form_id is not None:
            print(f"    -> Found base form '{base_form_name}' with ID {base_form_id}, remapping")
            # build new name as "{base_id}-{suffix}", where suffix is whatever came after
            # the first '-' in the original alt-form name
            suffix = v.split("-", 1)[1] if "-" in v else ""
            results[k] = f"{base_form_id}-{suffix}" if suffix else results[base_form_id]
            print(f"    -> New mapping: {k} -> {results[k]}")
    return results


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
    if showdown_name in known_names:
        return showdown_name
    base, _ = resolve_alt_form_name(showdown_name)
    if base in known_names:
        return base
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
        print(f"Mapping alt form ID {pid} to base form name '{base_name}'")
        base_name_id = name_to_id.get(base_name.split("-", 1)[0])
        print(f"  -> base form ID is '{base_name_id}'")
        if base_name_id is None:
            print(f"Error: Could not find base form ID for alt form '{base_name}' (sprite name '{sprite_name}').")
            exit(1)
        return name_to_id.get(base_name, pid)
    return pid


if __name__ == "__main__":
    pokemon_list = list_pokemon()
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
        remote_to_species = build_showdown_to_species_map(showdown_index, name_to_id)

        print(f"\n{'=' * 40}\nMissing images in folder: {folder}\n{'=' * 40}\n")

        remaining: set[str] = set()

        for pid, name in pokemon_list.items():

            candidates = [remote for remote, species in remote_to_species.items() if species == name]

            if candidates:
                # Download all matching candidates (no interactive prompt)
                chosen_list = candidates
                for chosen in chosen_list:
                    save_id = resolve_save_id(pid, chosen, name_to_id)
                    if int(save_id) > 10000:
                        print(f"WARNING: Saving alt form with alt form ID {save_id}, consider mapping to base form ID instead.")
                    suffix = f"-{chosen.split('-', 1)[1]}" if '-' in chosen else ''
                    print(f"SAVED FILE NAME: {save_id}{suffix}.gif")
                    if not DRY_RUN:
                        download_image(
                            f"{save_id}{suffix}",
                            chosen,
                            folder,
                            f"{_construct_showdown_url(back=back, shiny=shiny)}/{chosen}.gif",
                        )
            else:
                print(f"No Showdown sprite found for {name} (ID={pid})")
                base_form = name.split("-", 1)
                base_form_name = base_form[0]
                base_candidates = [remote for remote, species in remote_to_species.items() if species == base_form_name]
                if base_candidates:
                    print(f"  -> but found base form sprite(s): {', '.join(base_candidates)}\n")
                    # Accept and download all base candidates automatically (no prompts)
                    for chosen in base_candidates:
                        print(f"     Accepted alternate form mapping '{name}' -> '{chosen}'")
                        save_id = resolve_save_id(pid, chosen, name_to_id)
                        if int(save_id) > 10000:
                            print(f"WARNING: Saving alt form with alt form ID {save_id}, consider mapping to base form ID instead.")
                        suffix = f"-{name.split('-', 1)[1]}" if '-' in name else ''
                        print(f"SAVED FILE NAME: {save_id}{suffix}.gif")
                        if not DRY_RUN:
                            download_image(
                                f"{save_id}{suffix}",
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
