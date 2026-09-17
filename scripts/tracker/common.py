from __future__ import annotations

import csv
import io
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# Ensure UTF-8 output encoding across all terminals
def reconfigure_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

reconfigure_utf8()

# Core Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SPRITES_DIR = PROJECT_ROOT / "sprites"
BASE_PATH = SPRITES_DIR / "pokemon"
WEBSITE_DIR = PROJECT_ROOT / "website"
TEMPLATES_DIR = SCRIPT_DIR / "templates"
CACHE_DIR = PROJECT_ROOT / ".cache" / "pokeapi_csv"

# PokéAPI GitHub Data Base URL
GITHUB_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"

# Unified generational folders in upstream PokéAPI repository
UNIFIED_VERSION_GROUPS: dict[str, str] = {
    "black-2-white-2": "black-white",
    "sun-moon": "ultra-sun-ultra-moon",
}

# Roman numeral conversion helper
ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

def roman_to_int(s: str) -> int:
    """Converts a Roman numeral string (e.g. 'viii' or 'IX') to an integer."""
    s = s.upper()
    total = 0
    prev = 0
    for ch in reversed(s):
        curr = ROMAN_VALUES.get(ch, 0)
        if curr >= prev:
            total += curr
        else:
            total -= curr
        prev = curr
    return total or 1

# Species where cosmetic forms have no visual differences across patterns in official games
VISUALLY_INVARIANT_FORM_SPECIES: set[str] = {"414", "664", "665"}


def get_candidate_stems(
    pokemon_id: int | str,
    form_id: int | str = "",
    name: str = "",
    is_form: bool = False,
    form_identifier: str = "",
) -> list[str]:
    """Computes unambiguous candidate file stems for a Pokémon variety or cosmetic form."""
    stems: list[str] = []
    p_id = str(pokemon_id)
    f_id = str(form_id) if form_id else ""

    if is_form:
        if form_identifier:
            stems.append(f"{p_id}-{form_identifier}")
        else:
            if f_id:
                stems.append(f_id)
            stems.append(p_id)
    else:
        stems.append(p_id)

    if is_form and name and name not in stems:
        stems.append(name)

    # Fallback to base species stem for visually invariant forms (e.g. Scatterbug and Spewpa)
    if is_form and p_id in VISUALLY_INVARIANT_FORM_SPECIES and p_id not in stems:
        stems.append(p_id)

    return stems


def load_csv(url: str, cache_name: str | None = None, max_age_seconds: int = 604800) -> list[dict[str, str]]:
    """Loads a remote CSV file into a list of dicts using Python stdlib with local disk caching.
    
    Defaults to 7 days cache expiration.
    """
    if not cache_name:
        cache_name = Path(url.split("?")[0]).name

    cache_file = CACHE_DIR / cache_name
    content: str = ""

    if cache_file.exists():
        try:
            mtime = cache_file.stat().st_mtime
            if time.time() - mtime < max_age_seconds:
                content = cache_file.read_text(encoding="utf-8")
        except Exception:
            content = ""

    if not content:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PokeAPISprites/2.0)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_data = resp.read()
                content = raw_data.decode("utf-8", errors="replace")
                try:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(content, encoding="utf-8")
                except Exception:
                    pass
        except Exception as e:
            if cache_file.exists():
                content = cache_file.read_text(encoding="utf-8")
            else:
                raise RuntimeError(f"Failed to fetch CSV from {url}: {e}") from e

    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


# ---------------------------------------------------------------------------
# Intentional sprite absence rules — shared by sprite_audit.py and
# build_sprite_index.py to prevent false negatives in the coverage tracker.
#
# Each rule is a dict with:
#   pokemon_id    : int        – PokéAPI Pokémon or Form ID
#   labels        : list[str]  – View labels to treat as intentionally absent
#   max_gen       : int        – (optional) apply rule when game gen_num <= max_gen
#   games         : list[str]  – (optional) apply rule ONLY for these game IDs
#   exclude_games : list[str]  – (optional) apply rule for all games EXCEPT these game IDs
# ---------------------------------------------------------------------------
SPRITE_EXCL_FEMALE_VIEWS: list[str] = [
    "Front Female", "Front Shiny Female", "Back Female", "Back Shiny Female",
    "Front Animated Female", "Front Animated Shiny Female",
    "Back Animated Female", "Back Animated Shiny Female",
]
SPRITE_EXCL_SHINY_VIEWS: list[str] = [
    "Front Shiny", "Front Shiny Female", "Back Shiny", "Back Shiny Female",
    "Front Animated Shiny", "Front Animated Shiny Female",
    "Back Animated Shiny", "Back Animated Shiny Female",
]
SPRITE_EXCL_ALL_VIEWS: list[str] = [
    "Front Default", "Front Shiny", "Front Female", "Front Shiny Female",
    "Back Default", "Back Shiny", "Back Female", "Back Shiny Female",
    "Front Animated", "Front Animated Default", "Front Animated Shiny",
    "Front Animated Female", "Front Animated Shiny Female",
    "Back Animated", "Back Animated Default", "Back Animated Shiny",
    "Back Animated Female", "Back Animated Shiny Female",
    "Menu Icon", "Menu Icon Female", "Icons", "Icon",
]

KNOWN_SPRITE_EXCLUSION_RULES: list[dict[str, Any]] = [
    # Eevee (#133): no female sprite differences before Gen VIII (SWSH)
    {
        "pokemon_id": 133,
        "labels": SPRITE_EXCL_FEMALE_VIEWS,
        "max_gen": 7,
    },
    # Pichu spiky-eared (form 10065): sprite only existed in HGSS
    {
        "pokemon_id": 10065,
        "labels": SPRITE_EXCL_ALL_VIEWS,
        "exclude_games": ["heartgold-soulsilver"],
    },
    # Arceus-unknown (form 10057): ??? type only existed in Gen IV (DP/Pt/HGSS)
    {
        "pokemon_id": 10057,
        "labels": SPRITE_EXCL_ALL_VIEWS,
        "exclude_games": ["diamond-pearl", "platinum", "heartgold-soulsilver"],
    },
    # Cherrim-sunshine (form 10038): battle-only form, has no separate menu icon
    {
        "pokemon_id": 10038,
        "labels": ["Menu Icon"],
    },
    # All castform weather forms (forms 10013, 10014, 10015): battle-only forms, have no separate menu icons
    {
        "pokemon_id": 10013,
        "labels": ["Menu Icon"],
    },
    {
        "pokemon_id": 10014,
        "labels": ["Menu Icon"],
    },
    {
        "pokemon_id": 10015,
        "labels": ["Menu Icon"],
    },
    # Partner Pikachu (#10158): shiny-locked in LGPE
    {
        "pokemon_id": 10158,
        "labels": SPRITE_EXCL_SHINY_VIEWS,
        "games": ["lets-go-pikachu-lets-go-eevee"],
    },
    # Partner Eevee (#10159): shiny-locked in LGPE
    {
        "pokemon_id": 10159,
        "labels": SPRITE_EXCL_SHINY_VIEWS,
        "games": ["lets-go-pikachu-lets-go-eevee"],
    },
    # Gen 3 Deoxys version-exclusivity:
    # RS: Normal form only (386). Speed (10003), Attack (10001), Defense (10002) not in RS.
    # FRLG: Attack (10001) in FR, Defense (10002) in LG. Speed (10003) only debuted in Emerald.
    # Emerald: Speed form (10003) only. Attack (10001) and Defense (10002) not in Emerald.
    {
        "pokemon_id": 10003,
        "labels": SPRITE_EXCL_ALL_VIEWS,
        "games": ["ruby-sapphire", "firered-leafgreen"],
    },
    {
        "pokemon_id": 10001,
        "labels": SPRITE_EXCL_ALL_VIEWS,
        "games": ["ruby-sapphire", "emerald"],
    },
    {
        "pokemon_id": 10002,
        "labels": SPRITE_EXCL_ALL_VIEWS,
        "games": ["ruby-sapphire", "emerald"],
    },
    # Cosplay Pikachu forms (10080-10085): only existed in ORAS (Gen 6), cannot be transferred
    *[
        {
            "pokemon_id": pid,
            "labels": SPRITE_EXCL_ALL_VIEWS,
            "exclude_games": ["omega-ruby-alpha-sapphire"],
        }
        for pid in (10080, 10081, 10082, 10083, 10084, 10085)
    ],
    # Cap Pikachu forms: event gifts in SM / USUM / SwSh / SV, intentionally absent in LGPE
    *[
        {
            "pokemon_id": pid,
            "labels": SPRITE_EXCL_ALL_VIEWS,
            "games": ["lets-go-pikachu-lets-go-eevee"],
        }
        for pid in (10094, 10095, 10096, 10097, 10098, 10099, 10148, 10160)
    ],
    # Totem Pokémon forms: SM / USUM exclusive, absent in LGPE and other games
    *[
        {
            "pokemon_id": pid,
            "labels": SPRITE_EXCL_ALL_VIEWS,
            "exclude_games": ["sun-moon", "ultra-sun-ultra-moon"],
        }
        for pid in (
            10093, 10121, 10122, 10128, 10129, 10144, 10145, 10146, 10149, 10150, 10153, 10154
        )
    ],
]


def compile_exclusions(game_id: str, gen_num: int) -> dict[int, frozenset[str]]:
    """Build a {pokemon_id -> frozenset(labels)} exclusion lookup for a specific game.

    Evaluates each rule in KNOWN_SPRITE_EXCLUSION_RULES and returns the labels
    that apply to this game based on max_gen, games, and exclude_games conditions.
    """
    base_game_id = game_id.replace("-icons", "")
    result: dict[int, set[str]] = {}
    for rule in KNOWN_SPRITE_EXCLUSION_RULES:
        max_gen = rule.get("max_gen")
        games = rule.get("games")
        exclude_games = rule.get("exclude_games")

        applies = True
        if max_gen is not None and gen_num > max_gen:
            applies = False
        if games is not None and game_id not in games and base_game_id not in games:
            applies = False
        if exclude_games is not None and (game_id in exclude_games or base_game_id in exclude_games):
            applies = False

        if applies:
            pk_id = rule["pokemon_id"]
            result.setdefault(pk_id, set()).update(rule["labels"])

    return {pk_id: frozenset(labels) for pk_id, labels in result.items()}
