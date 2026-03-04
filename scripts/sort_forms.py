import json
import re
from pathlib import Path


def sort_key(key):
    """
    Sort order:
    1. Main numeric part
    2. No suffix
    3. Numeric suffix (_2)
    4. Letter suffix (668m, 876f)
    5. Other suffixes (_g, etc.)
    """
    key = str(key)

    match = re.match(r"^(\d+)", key)
    if not match:
        return (float("inf"), 4, key)

    main_number = int(match.group(1))
    rest = key[len(match.group(1)) :]

    if rest == "":
        return (main_number, 0, 0)

    if rest.startswith("_"):
        suffix = rest[1:]
        if suffix.isdigit():
            return (main_number, 1, int(suffix))
        else:
            return (main_number, 3, suffix)

    if rest.isalpha():
        return (main_number, 2, rest)

    return (main_number, 4, rest)


def main():
    # Get directory where this script lives
    script_dir = Path(__file__).resolve().parent

    # Build absolute path to scripts/forms.json
    json_path = script_dir / "forms.json"

    if not json_path.exists():
        raise FileNotFoundError(f"Could not find file at: {json_path}")

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Sort
    sorted_items = sorted(data.items(), key=lambda x: sort_key(x[0]))
    sorted_dict = dict(sorted_items)

    # Overwrite same file
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_dict, f, indent=4, ensure_ascii=False)

    print(f"{json_path} sorted successfully.")


if __name__ == "__main__":
    main()
