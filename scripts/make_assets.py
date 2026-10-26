"""
Generate Vizier branding assets with Pillow.

Usage::

    python scripts/make_assets.py

Produces ``assets/vizier.ico`` (multi-resolution), ``assets/vizier.png``,
``assets/vizier-banner.png`` and the two Inno Setup wizard bitmaps.  Kept in
the repo so releases are reproducible.

The mark is an original midnight-palace seal: a gilded pointed arch around a
star, with a crimson jewel.  The wordmark uses Rakkas (SIL OFL), bundled at
``assets/fonts/Rakkas-Regular.ttf``.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT_PATH = ASSETS / "fonts" / "Rakkas-Regular.ttf"
ASSETS.mkdir(exist_ok=True)

INK = (11, 10, 23, 255)
INK_TOP = (24, 20, 45, 255)
INK_DEEP = (7, 6, 14, 255)
SURFACE = (23, 20, 42, 255)
GOLD = (212, 168, 87, 255)
GOLD_BRIGHT = (242, 215, 154, 255)
GOLD_PALE = (248, 235, 200, 255)
GOLD_DEEP = (140, 106, 42, 255)
CRIMSON = (142, 27, 44, 255)
CRIMSON_BRIGHT = (200, 50, 74, 255)
TURQUOISE = (79, 209, 197, 255)
IVORY = (245, 239, 226, 255)
IVORY_DIM = (185, 178, 199, 255)
IVORY_MUTED = (129, 122, 146, 255)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _display_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        for name in ("georgiab.ttf", "seguisb.ttf", "segoeui.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()


def _ui_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ("seguisb.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _vertical_gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        colour = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(4))
        draw.line((0, y, width, y), fill=colour)
    return image


def _bezier(p0, p1, p2, steps: int = 80):
    points = []
    for step in range(steps + 1):
        t = step / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        points.append((x, y))
    return points


def _arch_points(left: float, right: float, top: float, base: float):
    middle = (left + right) / 2
    shoulder = top + (base - top) * 0.52
    points = [(left, base)]
    points += _bezier((left, shoulder), (left, top + (base - top) * 0.18), (middle, top))
    points += _bezier(
        (middle, top), (right, top + (base - top) * 0.18), (right, shoulder)
    )[1:]
    points.append((right, base))
    return points


def _star_points(cx: float, cy: float, outer: float, inner: float, points: int = 8):
    vertices = []
    for index in range(points * 2):
        angle = -math.pi / 2 + index * math.pi / points
        radius = outer if index % 2 == 0 else inner
        vertices.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return vertices


def _draw_star(draw: ImageDraw.ImageDraw, cx, cy, outer, inner, fill, outline=None, width=1):
    vertices = _star_points(cx, cy, outer, inner)
    draw.polygon(vertices, fill=fill, outline=outline, width=width)


def _tracked_text(
    draw: ImageDraw.ImageDraw,
    centre_x: float,
    baseline: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill,
    tracking: float,
):
    widths = [font.getlength(char) for char in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = centre_x - total / 2
    for char, width in zip(text, widths, strict=True):
        draw.text((x, baseline), char, font=font, fill=fill, anchor="ls")
        x += width + tracking


def _gradient_wordmark(
    image: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    position: tuple[float, float],
    anchor: str = "ls",
) -> None:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).text(position, text, font=font, fill=255, anchor=anchor)
    bbox = mask.getbbox()
    if bbox is None:
        return
    gradient = _vertical_gradient(
        image.size, GOLD_PALE, GOLD_DEEP
    )
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer.paste(gradient, (0, 0), mask)
    # A soft glow makes the gold read against the midnight field.
    glow = mask.filter(ImageFilter.GaussianBlur(6))
    halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
    halo.paste(Image.new("RGBA", image.size, (242, 215, 154, 90)), (0, 0), glow)
    image.alpha_composite(halo)
    image.alpha_composite(layer)


# ---------------------------------------------------------------------------
# Artwork
# ---------------------------------------------------------------------------

def make_icon(size: int = 1024) -> Image.Image:
    """Draw the Vizier seal: a gilded arch, star, and crimson jewel."""
    scale = size / 1024.0

    def s(value: float) -> float:
        return value * scale

    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient = _vertical_gradient((size, size), INK_TOP, INK_DEEP)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (s(18), s(18), s(1006), s(1006)), radius=s(210), fill=255
    )
    tile.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(tile)

    # Double gold frame.
    draw.rounded_rectangle(
        (s(18), s(18), s(1006), s(1006)),
        radius=s(210),
        outline=GOLD,
        width=max(2, int(s(14))),
    )
    draw.rounded_rectangle(
        (s(58), s(58), s(966), s(966)),
        radius=s(176),
        outline=(140, 106, 42, 210),
        width=max(1, int(s(4))),
    )

    # Glow behind the star.
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        (s(250), s(300), s(774), s(824)),
        fill=(212, 168, 87, 32),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(s(55)))
    tile.alpha_composite(glow)

    # Pointed arch.
    arch = _arch_points(s(252), s(772), s(258), s(824))
    draw.line(arch, fill=GOLD, width=max(3, int(s(20))), joint="curve")
    inner_arch = _arch_points(s(286), s(738), s(300), s(806))
    draw.line(inner_arch, fill=(140, 106, 42, 220), width=max(1, int(s(5))), joint="curve")

    # The star and its jewel.
    _draw_star(
        draw, s(512), s(590), s(154), s(58), GOLD_BRIGHT,
        outline=GOLD_DEEP, width=max(1, int(s(4))),
    )
    draw.ellipse(
        (s(468), s(546), s(556), s(634)),
        fill=CRIMSON,
        outline=GOLD_PALE,
        width=max(1, int(s(6))),
    )
    draw.ellipse((s(500), s(578), s(524), s(602)), fill=TURQUOISE)

    # Apex finial.
    _draw_star(draw, s(512), s(214), s(28), s(10), GOLD_PALE)

    # Banner base.
    draw.rounded_rectangle(
        (s(236), s(852), s(788), s(922)),
        radius=s(14),
        fill=(92, 15, 29, 235),
        outline=GOLD,
        width=max(1, int(s(5))),
    )
    _draw_star(draw, s(512), s(887), s(18), s(6), GOLD_BRIGHT)
    draw.line(
        (s(286), s(887), s(478), s(887)),
        fill=(212, 168, 87, 150),
        width=max(1, int(s(2))),
    )
    draw.line(
        (s(546), s(887), s(738), s(887)),
        fill=(212, 168, 87, 150),
        width=max(1, int(s(2))),
    )
    return tile


def make_banner(width: int = 1400, height: int = 360) -> Image.Image:
    """Wide banner used in the README and release page."""
    base = _vertical_gradient((width, height), INK_TOP, INK_DEEP)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    width_arch = 200
    x = -width_arch * 0.4
    while x < width:
        od.line(
            _arch_points(x, x + width_arch, 34, 370),
            fill=(212, 168, 87, 30),
            width=2,
            joint="curve",
        )
        x += width_arch + 42
    for index in range(30):
        sx = (index * 149.7 + 41) % width
        sy = (index * 97.3 + 23) % height
        _draw_star(od, sx, sy, 3.0, 1.0, (242, 215, 154, 34))
    base.alpha_composite(overlay)

    icon = make_icon(340)
    base.alpha_composite(icon, (52, (height - 340) // 2))

    wordmark = _display_font(168)
    _gradient_wordmark(base, "VIZIER", wordmark, (430, 188))
    draw = ImageDraw.Draw(base)

    _tracked_text(
        draw, 430 + wordmark.getlength("VIZIER") / 2, 230,
        "THE ROYAL ADVISOR", _ui_font(24, bold=True), GOLD_BRIGHT, 7.0,
    )
    draw.line((430, 264, 1310, 264), fill=(212, 168, 87, 90), width=1)
    draw.text(
        (430, 292),
        "100% local AI agent   ·   no cloud   ·   no BYOK   ·   no telemetry",
        font=_ui_font(22),
        fill=IVORY_DIM,
    )
    draw.text(
        (430, 330),
        "MIDNIGHT COURT EDITION",
        font=_ui_font(15, bold=True),
        fill=TURQUOISE,
    )
    draw.rectangle((0, 0, 8, height), fill=GOLD_DEEP)
    draw.rectangle((0, height - 5, width, height), fill=(92, 15, 29, 255))
    return base


def make_wizard_large(width: int = 164, height: int = 314) -> Image.Image:
    """Left-hand artwork for the Inno Setup installer wizard."""
    base = _vertical_gradient((width, height), INK_TOP, INK_DEEP).convert("RGB")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.line(
        _arch_points(16, 148, 22, 300),
        fill=(212, 168, 87, 45),
        width=1,
        joint="curve",
    )
    for index in range(9):
        sx = (index * 61 + 17) % width
        sy = (index * 83 + 31) % height
        _draw_star(od, sx, sy, 2.2, 0.8, (242, 215, 154, 60))
    base = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(base)

    draw.rectangle((0, 0, width - 1, height - 1), outline=(212, 168, 87, 70))
    icon = make_icon(128).resize((96, 96), Image.LANCZOS)
    base.alpha_composite(icon, ((width - 96) // 2, 34))

    wordmark = _display_font(30)
    if wordmark.getlength("VIZIER") > width - 16:
        wordmark = _display_font(25)
    _gradient_wordmark(base, "VIZIER", wordmark, (width / 2, 160), anchor="ms")
    draw = ImageDraw.Draw(base)
    _tracked_text(
        draw, width / 2, 182, "THE ROYAL ADVISOR", _ui_font(8, bold=True),
        GOLD, 1.2,
    )
    draw.line((28, 198, width - 28, 198), fill=(212, 168, 87, 90), width=1)
    _tracked_text(
        draw, width / 2, 222, "LOCAL", _ui_font(9, bold=True), TURQUOISE, 1.5,
    )
    _tracked_text(
        draw, width / 2, 240, "NO CLOUD", _ui_font(7, bold=True), IVORY_MUTED, 1.0,
    )
    _tracked_text(
        draw, width / 2, 256, "NO TELEMETRY", _ui_font(7, bold=True), IVORY_MUTED, 1.0,
    )
    _draw_star(draw, width / 2, 282, 7, 2.5, GOLD_BRIGHT)
    return base.convert("RGB")


def make_wizard_small(size: int = 55) -> Image.Image:
    base = _vertical_gradient((size, size), INK_TOP, INK_DEEP).convert("RGB")
    icon = make_icon(128).resize((size - 6, size - 6), Image.LANCZOS)
    base = base.convert("RGBA")
    base.alpha_composite(icon, (3, 3))
    return base.convert("RGB")


def main() -> None:
    icon = make_icon()
    icon.resize((512, 512), Image.LANCZOS).save(ASSETS / "vizier.png")
    icon.save(
        ASSETS / "vizier.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    make_banner().convert("RGB").save(ASSETS / "vizier-banner.png")
    make_wizard_large().save(ASSETS / "wizard-large.bmp")
    make_wizard_small().save(ASSETS / "wizard-small.bmp")
    print("Wrote:")
    for name in (
        "vizier.ico",
        "vizier.png",
        "vizier-banner.png",
        "wizard-large.bmp",
        "wizard-small.bmp",
    ):
        path = ASSETS / name
        print(f"  {path} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
