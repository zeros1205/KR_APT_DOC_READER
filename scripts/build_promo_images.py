"""
Generate store listing promo images for 정과장의 청약노트.

Two output sets are produced because Google Play and Apple App Store
require different sizes:

- Google Play Store: 1080 x 1920 (9:16, the safe portrait spec)
- Apple App Store:   1290 x 2796 (iPhone 6.7" — currently required)

Style reference: Google NotebookLM Play Store promo cards.
- Bold Korean headline at the top, with keywords drawn in a brand-color
  gradient (orange → deep red, matching the app palette).
- A device mockup beneath the headline, containing the actual app screenshot.
- Warm cream background, matching the app's brand palette.

Outputs:
    docs/promo/out/play/*.png
    docs/promo/out/ios/*.png
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SCREENS_DIR = ROOT / "docs" / "promo" / "screenshots"
OUT_DIR = ROOT / "docs" / "promo" / "out"

FONT_DIR = ROOT / "docs" / "promo" / "assets" / "fonts"
PRETENDARD_BLACK = str(FONT_DIR / "Pretendard-Black.otf")
PRETENDARD_EXTRABOLD = str(FONT_DIR / "Pretendard-ExtraBold.otf")
PRETENDARD_BOLD = str(FONT_DIR / "Pretendard-Bold.otf")
PRETENDARD_SEMIBOLD = str(FONT_DIR / "Pretendard-SemiBold.otf")
PRETENDARD_MEDIUM = str(FONT_DIR / "Pretendard-Medium.otf")
PRETENDARD_REGULAR = str(FONT_DIR / "Pretendard-Regular.otf")

# Active headline weight — Pretendard SemiBold (600)
HEADLINE_FACE = PRETENDARD_SEMIBOLD
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------

BG_COLOR = (250, 246, 240)          # warm cream, matches the app
INK_PRIMARY = (28, 24, 22)
INK_SECONDARY = (110, 100, 90)
GRAD_A = (245, 138, 70)             # orange
GRAD_B = (216, 80, 50)              # deep red — keyword gradient endpoint

FRAME_COLOR = (24, 22, 20)


# ---------------------------------------------------------------------------
# Canvas spec — describes a target store size
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CanvasSpec:
    name: str
    width: int
    height: int

    # Layout (computed lazily as fractions of width/height)
    @property
    def out_dir(self) -> Path:
        d = OUT_DIR / self.name
        d.mkdir(parents=True, exist_ok=True)
        return d

    # Headline metrics — sized off width so long Korean lines never overflow
    @property
    def headline_size(self) -> int:
        return int(self.width * 0.085)

    @property
    def headline_top(self) -> int:
        return int(self.height * 0.075)

    @property
    def line_height(self) -> int:
        return int(self.headline_size * 1.32)

    # Phone mockup
    @property
    def phone_width(self) -> int:
        return int(self.width * 0.74)

    @property
    def phone_top(self) -> int:
        return int(self.height * 0.30)

    @property
    def frame_radius(self) -> int:
        return int(self.width * 0.07)

    @property
    def frame_thickness(self) -> int:
        return int(self.width * 0.018)

    # Text-only intro layout — width-bound for headline width safety
    @property
    def intro_headline_size(self) -> int:
        return int(self.width * 0.1088)

    @property
    def intro_headline_top(self) -> int:
        return int(self.height * 0.10)

    @property
    def intro_line_height(self) -> int:
        return int(self.intro_headline_size * 1.30)

    @property
    def intro_tagline_size(self) -> int:
        return int(self.width * 0.0978)

    @property
    def intro_tagline_top(self) -> int:
        return int(self.height * 0.74)

    @property
    def intro_tagline_line_height(self) -> int:
        return int(self.intro_tagline_size * 1.32)


PLAY_SPEC = CanvasSpec(name="play", width=1080, height=1920)
IOS_SPEC = CanvasSpec(name="ios", width=1290, height=2796)


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

def kfont(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def emoji_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(EMOJI_FONT, size=size)
    except OSError:
        return ImageFont.truetype(EMOJI_FONT, size=109)


# ---------------------------------------------------------------------------
# Headline rendering — supports gradient keywords and emoji segments
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    text: str
    gradient: bool = False
    is_emoji: bool = False


@dataclass
class HeadlineLine:
    segments: list[Segment]


def _measure(seg: Segment, font: ImageFont.FreeTypeFont,
             emoji: ImageFont.FreeTypeFont) -> tuple[int, int]:
    f = emoji if seg.is_emoji else font
    bbox = f.getbbox(seg.text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _gradient_swatch(width: int, height: int) -> Image.Image:
    grad = Image.new("RGB", (max(width, 1), max(height, 1)), GRAD_A)
    px = grad.load()
    for x in range(grad.width):
        t = x / max(grad.width - 1, 1)
        r = int(GRAD_A[0] + (GRAD_B[0] - GRAD_A[0]) * t)
        g = int(GRAD_A[1] + (GRAD_B[1] - GRAD_A[1]) * t)
        b = int(GRAD_A[2] + (GRAD_B[2] - GRAD_A[2]) * t)
        for y in range(grad.height):
            px[x, y] = (r, g, b)
    return grad


def _paste_segment(canvas: Image.Image, x: int, y: int, seg: Segment,
                   font: ImageFont.FreeTypeFont,
                   emoji: ImageFont.FreeTypeFont) -> int:
    if seg.is_emoji:
        target_h = font.size
        native = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(native).text((0, 0), seg.text, font=emoji,
                                    embedded_color=True)
        bbox = native.getbbox()
        if bbox is None:
            return 0
        em = native.crop(bbox)
        scale = target_h / em.height
        new_w = int(em.width * scale)
        new_h = int(em.height * scale)
        em = em.resize((new_w, new_h), Image.LANCZOS)
        offset_y = y + (font.size - new_h) // 2
        canvas.paste(em, (x, offset_y), em)
        return new_w + int(font.size * 0.08)

    w, _ = _measure(seg, font, emoji)
    if seg.gradient:
        ascent, descent = font.getmetrics()
        mask_h = ascent + descent + 20
        mask = Image.new("L", (w + 8, mask_h), 0)
        ImageDraw.Draw(mask).text((4, 0), seg.text, font=font, fill=255)
        swatch = _gradient_swatch(mask.width, mask.height)
        canvas.paste(swatch, (x - 4, y), mask)
    else:
        ImageDraw.Draw(canvas).text((x, y), seg.text, font=font,
                                    fill=INK_PRIMARY)
    return w


def draw_headline(canvas: Image.Image, lines: list[HeadlineLine],
                  font: ImageFont.FreeTypeFont,
                  emoji: ImageFont.FreeTypeFont,
                  top: int, line_height: int) -> int:
    y = top
    for line in lines:
        widths = []
        for seg in line.segments:
            if seg.is_emoji:
                widths.append(int(font.size * 1.05))
            else:
                widths.append(_measure(seg, font, emoji)[0])
        total = sum(widths)
        x = (canvas.width - total) // 2
        for seg, w in zip(line.segments, widths):
            advance = _paste_segment(canvas, x, y, seg, font, emoji)
            x += advance if advance else w
        y += line_height
    return y


# ---------------------------------------------------------------------------
# Phone mockup
# ---------------------------------------------------------------------------

def make_phone_mockup(screenshot_path: Path, spec: CanvasSpec) -> Image.Image:
    shot = Image.open(screenshot_path).convert("RGB")
    inner_w = spec.phone_width - spec.frame_thickness * 2
    scale = inner_w / shot.width
    inner_h = int(shot.height * scale)
    shot = shot.resize((inner_w, inner_h), Image.LANCZOS)

    frame_w = inner_w + spec.frame_thickness * 2
    frame_h = inner_h + spec.frame_thickness * 2

    frame = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle(
        (0, 0, frame_w, frame_h),
        radius=spec.frame_radius, fill=FRAME_COLOR + (255,),
    )

    inner_radius = max(spec.frame_radius - spec.frame_thickness + 6, 12)
    mask = Image.new("L", (inner_w, inner_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, inner_w, inner_h), radius=inner_radius, fill=255
    )
    frame.paste(shot, (spec.frame_thickness, spec.frame_thickness), mask)

    shadow_pad = int(spec.width * 0.06)
    shadow = Image.new("RGBA",
                       (frame_w + shadow_pad * 2, frame_h + shadow_pad * 2),
                       (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (shadow_pad, shadow_pad + 16,
         shadow_pad + frame_w, shadow_pad + frame_h + 16),
        radius=spec.frame_radius, fill=(0, 0, 0, 64),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(spec.width * 0.025)))
    shadow.alpha_composite(frame, (shadow_pad, shadow_pad))
    return shadow


# ---------------------------------------------------------------------------
# Promo builders
# ---------------------------------------------------------------------------

def new_canvas(spec: CanvasSpec) -> Image.Image:
    return Image.new("RGB", (spec.width, spec.height), BG_COLOR)


def build_promo_intro(spec: CanvasSpec, out_path: Path) -> None:
    canvas = new_canvas(spec)
    headline_font = kfont(HEADLINE_FACE, spec.intro_headline_size)
    tagline_font = kfont(HEADLINE_FACE, spec.intro_tagline_size)
    emoji = emoji_font(spec.intro_headline_size - 8)

    lines = [
        HeadlineLine([Segment("복잡한 분양 공고를")]),
        HeadlineLine([
            Segment("정과장이 깔끔히 "),
            Segment("📑", is_emoji=True),
        ]),
        HeadlineLine([Segment("정리해드려요")]),
    ]
    draw_headline(canvas, lines, headline_font, emoji,
                  top=spec.intro_headline_top,
                  line_height=spec.intro_line_height)

    tagline = [
        HeadlineLine([Segment("정과장의", gradient=True)]),
        HeadlineLine([Segment("청약노트", gradient=True)]),
    ]
    draw_headline(canvas, tagline, tagline_font, emoji,
                  top=spec.intro_tagline_top,
                  line_height=spec.intro_tagline_line_height)

    canvas.save(out_path, "PNG", optimize=True)


def build_promo_with_phone(
    spec: CanvasSpec,
    out_path: Path,
    headline_lines: list[HeadlineLine],
    screenshot: Path,
) -> None:
    canvas = new_canvas(spec)
    body = kfont(HEADLINE_FACE, spec.headline_size)
    emoji = emoji_font(spec.headline_size - 8)
    draw_headline(canvas, headline_lines, body, emoji,
                  top=spec.headline_top, line_height=spec.line_height)

    phone = make_phone_mockup(screenshot, spec)
    x = (canvas.width - phone.width) // 2
    canvas.paste(phone, (x, spec.phone_top), phone)
    canvas.save(out_path, "PNG", optimize=True)


def build_set(spec: CanvasSpec) -> None:
    out = spec.out_dir

    build_promo_intro(spec, out / "01_intro.png")

    build_promo_with_phone(
        spec, out / "02_regions.png",
        headline_lines=[
            HeadlineLine([
                Segment("관심 지역의 "),
                Segment("새 공고", gradient=True),
            ]),
            HeadlineLine([
                Segment("가장 먼저 받아보세요 "),
                Segment("📍", is_emoji=True),
            ]),
        ],
        screenshot=SCREENS_DIR / "02_regions.png",
    )

    build_promo_with_phone(
        spec, out / "03_home.png",
        headline_lines=[
            HeadlineLine([
                Segment("복잡한 "),
                Segment("분양 정보", gradient=True),
                Segment("를"),
            ]),
            HeadlineLine([
                Segment("한눈에 정리해드려요 "),
                Segment("📑", is_emoji=True),
            ]),
        ],
        screenshot=SCREENS_DIR / "01_home.png",
    )

    build_promo_with_phone(
        spec, out / "04_notify.png",
        headline_lines=[
            HeadlineLine([
                Segment("신규 "),
                Segment("청약 공고", gradient=True),
                Segment("를"),
            ]),
            HeadlineLine([
                Segment("푸시 알림으로 "),
                Segment("🔔", is_emoji=True),
            ]),
        ],
        screenshot=SCREENS_DIR / "03_notify.png",
    )

    build_promo_with_phone(
        spec, out / "05_favorites.png",
        headline_lines=[
            HeadlineLine([
                Segment("관심 단지를 "),
                Segment("저장", gradient=True),
                Segment("하고"),
            ]),
            HeadlineLine([
                Segment("한눈에 비교하세요 "),
                Segment("⭐", is_emoji=True),
            ]),
        ],
        screenshot=SCREENS_DIR / "05_favorites.png",
    )


def main() -> None:
    for spec in (PLAY_SPEC, IOS_SPEC):
        build_set(spec)

    print("Wrote:")
    for p in sorted(OUT_DIR.rglob("*.png")):
        print(" -", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
