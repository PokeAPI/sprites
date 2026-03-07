# python .\pad_to_canvas.py --input ../sprites/pokemon/versions/generation-viii/brilliant-diamond-shining-pearl --output ../sprites/pokemon/versions/generation-viii/brilliant-diamond-shining-pearl_padded

import os
import argparse
from PIL import Image


def pad_images(input_folder, output_folder, canvas_size):
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if not filename.lower().endswith(".png"):
            continue

        img_path = os.path.join(input_folder, filename)
        img = Image.open(img_path).convert("RGBA")  # keep transparency

        # skip images that are taller than the canvas
        if img.height > canvas_size:
            print(f"Skipping {filename} (height {img.height}px > {canvas_size}px)")
            continue

        # create transparent canvas
        canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

        # bottom-center placement
        x = (canvas_size - img.width) // 2
        y = canvas_size - img.height

        canvas.paste(img, (x, y), img)

        out_path = os.path.join(output_folder, filename)
        canvas.save(out_path)

        print(f"Saved: {out_path}")

    print("Done!")


# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Pad images to a transparent square canvas."
    )
    parser.add_argument("--input", required=True, help="Input folder path")
    parser.add_argument("--output", required=True, help="Output folder path")
    parser.add_argument(
        "--size", type=int, default=256, help="Canvas size (default: 256)"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    pad_images(args.input, args.output, args.size)
