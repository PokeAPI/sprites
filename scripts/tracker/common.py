from __future__ import annotations

import csv
import io
import os
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
