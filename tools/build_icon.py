"""Generate release icons from a PNG source or a built-in fallback design."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
SOURCE_ICON = ASSETS_DIR / "app-icon.png"
BUILD_DIR = ROOT / "build"
OUTPUT_PNG = BUILD_DIR / "app-icon.png"
OUTPUT_ICO = BUILD_DIR / "app-icon.ico"


def create_default_icon(size: int = 1024) -> Image.Image:
    """Create a simple card-themed icon when no custom PNG is provided."""
    image = Image.new("RGBA", (size, size), "#0E2236")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        [(size * 0.06, size * 0.06), (size * 0.94, size * 0.94)],
        radius=size * 0.18,
        fill="#12314A",
        outline="#6BC3FF",
        width=max(8, size // 48),
    )

    back_card = [(size * 0.22, size * 0.18), (size * 0.68, size * 0.74)]
    front_card = [(size * 0.34, size * 0.28), (size * 0.80, size * 0.84)]
    art_panel = [(size * 0.40, size * 0.36), (size * 0.74, size * 0.64)]

    draw.rounded_rectangle(
        back_card,
        radius=size * 0.05,
        fill="#1A4A6C",
        outline="#9BE3FF",
        width=max(8, size // 56),
    )
    draw.rounded_rectangle(
        front_card,
        radius=size * 0.05,
        fill="#F8FBFF",
        outline="#F0BA52",
        width=max(10, size // 44),
    )
    draw.rounded_rectangle(
        art_panel,
        radius=size * 0.03,
        fill="#14324D",
    )

    draw.line(
        [(size * 0.42, size * 0.70), (size * 0.72, size * 0.70)],
        fill="#F0BA52",
        width=max(8, size // 50),
    )
    draw.line(
        [(size * 0.42, size * 0.76), (size * 0.66, size * 0.76)],
        fill="#A8B8C8",
        width=max(8, size // 62),
    )

    spark = [
        (size * 0.57, size * 0.40),
        (size * 0.61, size * 0.49),
        (size * 0.70, size * 0.53),
        (size * 0.61, size * 0.57),
        (size * 0.57, size * 0.66),
        (size * 0.53, size * 0.57),
        (size * 0.44, size * 0.53),
        (size * 0.53, size * 0.49),
    ]
    draw.polygon(spark, fill="#6FE1FF")

    return image


def normalize_icon_source(image: Image.Image, size: int = 1024) -> Image.Image:
    """Pad the source image onto a square canvas so it converts cleanly to ICO."""
    fitted = ImageOps.contain(image.convert("RGBA"), (size, size))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - fitted.width) // 2, (size - fitted.height) // 2)
    canvas.paste(fitted, offset, fitted)
    return canvas


def main() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if SOURCE_ICON.exists():
        image = normalize_icon_source(Image.open(SOURCE_ICON))
        source_label = SOURCE_ICON
    else:
        image = create_default_icon()
        source_label = "generated fallback"

    image.save(OUTPUT_PNG, format="PNG")
    image.save(
        OUTPUT_ICO,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )

    print(f"Icon source: {source_label}")
    print(f"Wrote {OUTPUT_PNG}")
    print(f"Wrote {OUTPUT_ICO}")


if __name__ == "__main__":
    main()
