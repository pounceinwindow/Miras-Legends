#!/usr/bin/env python3
import argparse
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
EDIT = ROOT / "edit"
FPS = 30

PALETTE = {
    "lime": "#B7FF00",
    "lime2": "#D9FF66",
    "green": "#073B3A",
    "deep": "#0C1E22",
    "cream": "#FFF5DB",
    "pink": "#FF2F9A",
    "gold": "#F2C14E",
    "white": "#FFFFFF",
    "muted": "#7E837A",
}

FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def clamp01(value):
    return max(0.0, min(1.0, value))


def font(path, size, scale):
    return ImageFont.truetype(path, max(10, round(size * scale)))


def rgba(hex_color, alpha=255):
    color = hex_color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def load_asset(path):
    return Image.open(path).convert("RGBA")


def contain(image, size, resample=Image.Resampling.LANCZOS):
    w, h = size
    ratio = min(w / image.width, h / image.height)
    result = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), resample)
    return result


def cover(image, size):
    w, h = size
    ratio = max(w / image.width, h / image.height)
    resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def paste_center(base, layer, center, opacity=1.0):
    if opacity < 1:
        layer = layer.copy()
        alpha = layer.getchannel("A").point(lambda p: round(p * opacity))
        layer.putalpha(alpha)
    x = round(center[0] - layer.width / 2)
    y = round(center[1] - layer.height / 2)
    base.alpha_composite(layer, (x, y))


def text_center(draw, text, y, fnt, fill, width, spacing=4, stroke=0, stroke_fill=None):
    box = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=spacing, align="center", stroke_width=stroke)
    tw = box[2] - box[0]
    draw.multiline_text(
        ((width - tw) / 2, y),
        text,
        font=fnt,
        fill=fill,
        spacing=spacing,
        align="center",
        stroke_width=stroke,
        stroke_fill=stroke_fill,
    )


class PromoRenderer:
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.s = width / 1080
        self.home = load_asset(ROOT / "artifacts/presentation-assets/home.png")
        self.map = load_asset(ROOT / "artifacts/presentation-assets/map.png")
        self.fight = load_asset(ROOT / "artifacts/presentation-assets/fight.png")
        self.pvp = load_asset(ROOT / "artifacts/presentation-assets/pvp.png")
        self.characters = {
            "su": load_asset(ROOT / "public/pixel/su-anasy.png"),
            "shurale": load_asset(ROOT / "public/pixel/shurale.png"),
            "syuyumbike": load_asset(ROOT / "public/pixel/syuyumbike.png"),
            "kereml": load_asset(ROOT / "public/pixel/kereml.png"),
        }
        self.logo = load_asset(ROOT / "resources/icon.png")
        self.grid = self.make_grid()

    def make_grid(self):
        img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        step = round(92 * self.s)
        for x in range(0, self.w + 1, step):
            d.line((x, 0, x, self.h), fill=rgba(PALETTE["green"], 32), width=max(1, round(2 * self.s)))
        for y in range(0, self.h + 1, step):
            d.line((0, y, self.w, y), fill=rgba(PALETTE["green"], 32), width=max(1, round(2 * self.s)))
        return img

    def background(self, color, grid=True):
        img = Image.new("RGBA", (self.w, self.h), rgba(color))
        if grid:
            img.alpha_composite(self.grid)
        return img

    def watermark(self, img, light=False):
        d = ImageDraw.Draw(img)
        color = PALETTE["cream"] if light else PALETTE["green"]
        d.text((54 * self.s, 55 * self.s), "МИРАС", font=font(FONT_BLACK, 39, self.s), fill=color)
        d.ellipse((43 * self.s, 112 * self.s, 51 * self.s, 120 * self.s), fill=PALETTE["pink"])

    def paper(self, img, y, h, angle=-2, color=None):
        layer = Image.new("RGBA", (round(self.w * 1.18), round(h * self.s)), rgba(color or PALETTE["cream"]))
        layer = layer.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        paste_center(img, layer, (self.w / 2, (y + h / 2) * self.s))

    def badge(self, img, text, y, fill=None, text_fill=None, angle=-2):
        fnt = font(FONT_BLACK, 28, self.s)
        tmp = Image.new("RGBA", (self.w, round(110 * self.s)), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        box = d.textbbox((0, 0), text, font=fnt)
        bw = box[2] - box[0] + round(58 * self.s)
        bh = round(70 * self.s)
        x = (self.w - bw) // 2
        d.rounded_rectangle((x, 5 * self.s, x + bw, 5 * self.s + bh), radius=10 * self.s, fill=fill or PALETTE["pink"])
        d.text((self.w / 2, 40 * self.s), text, font=fnt, fill=text_fill or PALETTE["white"], anchor="mm")
        tmp = tmp.rotate(angle, resample=Image.Resampling.BICUBIC)
        paste_center(img, tmp, (self.w / 2, y * self.s))

    def phone(self, img, screenshot, center_x, top, width, progress=1, angle=0, crop_top=0):
        width_px = round(width * self.s)
        aspect = screenshot.height / screenshot.width
        height_px = round(width_px * aspect)
        screen = screenshot.crop((0, crop_top, screenshot.width, screenshot.height)) if crop_top else screenshot
        screen = cover(screen, (width_px, height_px))
        radius = round(54 * self.s)
        mask = Image.new("L", screen.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, screen.width, screen.height), radius=radius, fill=255)
        screen.putalpha(mask)
        border = round(15 * self.s)
        phone = Image.new("RGBA", (screen.width + border * 2, screen.height + border * 2), (0, 0, 0, 0))
        pd = ImageDraw.Draw(phone)
        pd.rounded_rectangle((0, 0, phone.width, phone.height), radius=radius + border, fill=PALETTE["white"])
        pd.rounded_rectangle((border // 2, border // 2, phone.width - border // 2, phone.height - border // 2), radius=radius + border // 2, outline=PALETTE["green"], width=border)
        phone.alpha_composite(screen, (border, border))
        shadow = Image.new("RGBA", phone.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((0, 0, phone.width, phone.height), radius=radius, fill=(0, 35, 30, 135))
        shadow = shadow.filter(ImageFilter.GaussianBlur(round(24 * self.s)))
        scale = 0.88 + 0.12 * ease_out(progress)
        target = (round(phone.width * scale), round(phone.height * scale))
        phone = phone.resize(target, Image.Resampling.LANCZOS)
        shadow = shadow.resize(target, Image.Resampling.LANCZOS)
        if angle:
            phone = phone.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
            shadow = shadow.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        cy = (top * self.s) + phone.height / 2 + (1 - ease_out(progress)) * 180 * self.s
        paste_center(img, shadow, (center_x * self.s + 18 * self.s, cy + 25 * self.s), 0.65)
        paste_center(img, phone, (center_x * self.s, cy))

    def character(self, img, key, center, size, progress=1, angle=0):
        char = self.characters[key]
        px = round(size * self.s * (0.65 + 0.35 * ease_out(progress)))
        char = contain(char, (px, px), Image.Resampling.NEAREST)
        if angle:
            char = char.rotate(angle, resample=Image.Resampling.NEAREST, expand=True)
        shadow = char.getchannel("A").filter(ImageFilter.GaussianBlur(round(15 * self.s)))
        glow = Image.new("RGBA", char.size, rgba(PALETTE["white"], 0))
        glow.putalpha(shadow.point(lambda p: min(210, p)))
        paste_center(img, glow, (center[0] * self.s, center[1] * self.s + 12 * self.s), 0.9)
        paste_center(img, char, (center[0] * self.s, center[1] * self.s))

    def hook(self, local, dur):
        p = local / dur
        img = self.background(PALETTE["deep"], True)
        d = ImageDraw.Draw(img)
        self.watermark(img, light=True)
        a = ease_out(local / 0.55)
        text_center(d, "МЫ ПРОИГРАЛИ", (355 + (1 - a) * 90) * self.s, font(FONT_BLACK, 74, self.s), PALETTE["cream"], self.w)
        a2 = ease_out((local - 0.28) / 0.55)
        text_center(d, "ХАКАТОН", (470 + (1 - a2) * 90) * self.s, font(FONT_BLACK, 115, self.s), PALETTE["pink"], self.w)
        if local > dur * 0.48:
            q = ease_out((local - dur * 0.48) / 0.45)
            self.paper(img, 690, 285, angle=2, color=PALETTE["lime"])
            d = ImageDraw.Draw(img)
            text_center(d, "НО ИГРУ\nНЕ ЗАКРЫЛИ", (730 + (1 - q) * 90) * self.s, font(FONT_BLACK, 72, self.s), PALETTE["green"], self.w, spacing=2)
        self.character(img, "shurale", (190, 1555), 410, clamp01((local - 0.55) / 0.6), -5)
        self.character(img, "su", (855, 1570), 450, clamp01((local - 0.72) / 0.6), 4)
        return img

    def brand(self, local, dur):
        img = self.background(PALETTE["lime"], True)
        self.paper(img, 180, 700, -2)
        d = ImageDraw.Draw(img)
        p = ease_out(local / 0.65)
        text_center(d, "МИРАС", (270 + (1 - p) * 100) * self.s, font(FONT_BLACK, 150, self.s), PALETTE["green"], self.w)
        text_center(d, "ЛЕГЕНДЫ КАЗАНИ", 500 * self.s, font(FONT_BLACK, 63, self.s), PALETTE["green"], self.w)
        text_center(d, "ОЖИВАЮТ РЯДОМ", 590 * self.s, font(FONT_BLACK, 67, self.s), PALETTE["pink"], self.w)
        keys = ["shurale", "su", "syuyumbike", "kereml"]
        xs = [155, 410, 680, 930]
        ys = [1320, 1410, 1350, 1420]
        sizes = [360, 410, 390, 340]
        for i, key in enumerate(keys):
            self.character(img, key, (xs[i], ys[i]), sizes[i], clamp01((local - 0.3 - i * 0.12) / 0.55), (-5 + i * 3))
        self.badge(img, "ТАТАРСКИЕ ЛЕГЕНДЫ · ИГРА В ГОРОДЕ", 1750, fill=PALETTE["green"], angle=-2)
        return img

    def map_scene(self, local, dur):
        img = self.background(PALETTE["cream"], True)
        d = ImageDraw.Draw(img)
        self.watermark(img)
        text_center(d, "ИЩИ ЛЕГЕНДЫ", 180 * self.s, font(FONT_BLACK, 72, self.s), PALETTE["green"], self.w)
        text_center(d, "НА КАРТЕ КАЗАНИ", 270 * self.s, font(FONT_BLACK, 72, self.s), PALETTE["pink"], self.w)
        self.phone(img, self.map, 540, 400, 690, clamp01(local / 0.7), angle=-2)
        pulse = 1 + 0.08 * math.sin(local * 7)
        self.character(img, "shurale", (885, 1530), 390 * pulse, clamp01((local - 0.45) / 0.5), 3)
        self.badge(img, "4 ТОЧКИ · ПЕРВЫЙ МАРШРУТ", 1780, angle=2)
        return img

    def encounter(self, local, dur):
        img = self.background(PALETTE["lime"], True)
        self.paper(img, 105, 330, -2)
        d = ImageDraw.Draw(img)
        text_center(d, "ВСТРЕЧАЙ", 155 * self.s, font(FONT_BLACK, 76, self.s), PALETTE["green"], self.w)
        text_center(d, "ХРАНИТЕЛЕЙ", 250 * self.s, font(FONT_BLACK, 90, self.s), PALETTE["pink"], self.w)
        self.phone(img, self.home, 350, 470, 620, clamp01(local / 0.65), angle=-3)
        self.character(img, "su", (820, 1195), 590, clamp01((local - 0.35) / 0.7), 3)
        self.badge(img, "ИСТОРИЯ → ИСПЫТАНИЕ → КОМАНДА", 1770, fill=PALETTE["green"], angle=-2)
        return img

    def battle(self, local, dur):
        img = self.background(PALETTE["deep"], True)
        d = ImageDraw.Draw(img)
        self.watermark(img, light=True)
        text_center(d, "ПОБЕЖДАЙ", 165 * self.s, font(FONT_BLACK, 82, self.s), PALETTE["cream"], self.w)
        text_center(d, "В ТРЁХ РУСЛАХ", 265 * self.s, font(FONT_BLACK, 76, self.s), PALETTE["lime"], self.w)
        self.phone(img, self.fight, 540, 430, 690, clamp01(local / 0.6), angle=1)
        if local > 0.8:
            q = (local - 0.8) % 0.85
            alpha = round(150 * (1 - clamp01(q / 0.55)))
            radius = (70 + q * 260) * self.s
            cx, cy = 540 * self.s, 1040 * self.s
            d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=rgba(PALETTE["pink"], alpha), width=max(2, round(12 * self.s)))
        self.badge(img, "БОЙ ДО 90 СЕКУНД", 1780, fill=PALETTE["pink"], angle=-2)
        return img

    def collection(self, local, dur):
        img = self.background(PALETTE["cream"], True)
        d = ImageDraw.Draw(img)
        self.watermark(img)
        text_center(d, "СОБИРАЙ", 180 * self.s, font(FONT_BLACK, 85, self.s), PALETTE["green"], self.w)
        text_center(d, "СВОЮ КОМАНДУ", 285 * self.s, font(FONT_BLACK, 79, self.s), PALETTE["pink"], self.w)
        self.phone(img, self.home, 540, 430, 700, clamp01(local / 0.65), angle=0)
        keys = ["shurale", "su", "syuyumbike", "kereml"]
        xs = [150, 415, 680, 930]
        for i, key in enumerate(keys):
            self.character(img, key, (xs[i], 1640), 315, clamp01((local - 0.35 - i * 0.1) / 0.45), (-4 + i * 2))
        return img

    def cta(self, local, dur):
        img = self.background(PALETTE["green"], True)
        d = ImageDraw.Draw(img)
        p = ease_out(local / 0.6)
        icon = contain(self.logo, (round(180 * self.s), round(180 * self.s)))
        paste_center(img, icon, (540 * self.s, (250 + (1 - p) * 100) * self.s))
        text_center(d, "МИРАС", 390 * self.s, font(FONT_BLACK, 135, self.s), PALETTE["cream"], self.w)
        text_center(d, "ИЩЕМ ПЕРВЫХ", 610 * self.s, font(FONT_BLACK, 70, self.s), PALETTE["lime"], self.w)
        text_center(d, "ТЕСТИРОВЩИКОВ", 705 * self.s, font(FONT_BLACK, 77, self.s), PALETTE["pink"], self.w)
        self.badge(img, "КАЗАНЬ · ПОДПИШИСЬ", 900, fill=PALETTE["cream"], text_fill=PALETTE["green"], angle=-2)
        keys = ["shurale", "su", "syuyumbike", "kereml"]
        xs = [160, 430, 700, 940]
        ys = [1440, 1510, 1440, 1510]
        sizes = [370, 430, 405, 345]
        for i, key in enumerate(keys):
            self.character(img, key, (xs[i], ys[i]), sizes[i], clamp01((local - 0.2 - i * 0.1) / 0.5), (-5 + i * 3))
        text_center(d, "ЛЕГЕНДЫ РЯДОМ", 1780 * self.s, font(FONT_BOLD, 34, self.s), PALETTE["cream"], self.w)
        return img

    def scene(self, kind, local, duration):
        return {
            "hook": self.hook,
            "brand": self.brand,
            "map": self.map_scene,
            "encounter": self.encounter,
            "battle": self.battle,
            "collection": self.collection,
            "cta": self.cta,
        }[kind](local, duration)


TIMELINES = {
    "22s": [
        ("hook", 2.6),
        ("brand", 2.6),
        ("map", 3.5),
        ("encounter", 3.3),
        ("battle", 4.8),
        ("collection", 2.5),
        ("cta", 2.7),
    ],
    "12s": [
        ("hook", 1.6),
        ("brand", 1.4),
        ("map", 2.1),
        ("battle", 3.0),
        ("collection", 1.8),
        ("cta", 2.1),
    ],
    "6s": [
        ("hook", 1.1),
        ("map", 1.3),
        ("battle", 1.8),
        ("cta", 1.8),
    ],
}


def make_audio(path, duration, boundaries):
    sr = 44100
    n = int(duration * sr)
    audio = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(42)

    def add(start, signal):
        i = max(0, int(start * sr))
        end = min(n, i + len(signal))
        if end > i:
            audio[i:end] += signal[: end - i]

    beat = 60 / 118
    for index, t in enumerate(np.arange(0, duration, beat / 2)):
        if index % 2 == 0:
            length = int(0.18 * sr)
            x = np.arange(length) / sr
            kick = np.sin(2 * np.pi * (88 * np.exp(-x * 18) + 42) * x) * np.exp(-x * 22) * 0.58
            add(t, kick)
        else:
            length = int(0.055 * sr)
            x = np.arange(length) / sr
            hat = rng.normal(0, 1, length) * np.exp(-x * 75) * 0.11
            add(t, hat)
        if index % 4 == 2:
            length = int(0.16 * sr)
            x = np.arange(length) / sr
            clap = rng.normal(0, 1, length) * np.exp(-x * 25) * 0.16
            add(t, clap)

    bass_notes = [55.0, 65.4, 49.0, 73.4]
    for index, t in enumerate(np.arange(0, duration, beat * 2)):
        length = int(min(beat * 1.7, duration - t) * sr)
        x = np.arange(length) / sr
        freq = bass_notes[index % len(bass_notes)]
        env = np.minimum(1, x * 18) * np.exp(-x * 1.8)
        bass = (np.sin(2 * np.pi * freq * x) + 0.28 * np.sin(2 * np.pi * freq * 2 * x)) * env * 0.12
        add(t, bass)

    for boundary in boundaries:
        length = int(0.42 * sr)
        x = np.arange(length) / sr
        noise = rng.normal(0, 1, length)
        envelope = np.sin(np.pi * np.clip(x / 0.42, 0, 1)) ** 2
        whoosh = noise * envelope * np.linspace(0.02, 0.16, length)
        add(max(0, boundary - 0.2), whoosh)

    # Soft limiter and 30 ms fades at output boundaries.
    audio = np.tanh(audio * 1.15)
    fade = int(0.03 * sr)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    stereo = np.stack([audio, audio], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        wav.writeframes(pcm.tobytes())


def render(version, width, height, crf, suffix):
    timeline = TIMELINES[version]
    duration = sum(item[1] for item in timeline)
    boundaries = []
    cursor = 0.0
    for _, scene_duration in timeline[:-1]:
        cursor += scene_duration
        boundaries.append(cursor)
    audio_path = EDIT / f"soundtrack-{version}.wav"
    output = EDIT / f"miras-promo-{version}{suffix}.mp4"
    make_audio(audio_path, duration, boundaries)
    renderer = PromoRenderer(width, height)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(FPS), "-i", "-",
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(output),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total_frames = round(duration * FPS)
    for frame_index in range(total_frames):
        t = frame_index / FPS
        elapsed = 0.0
        kind = timeline[-1][0]
        local = 0.0
        scene_duration = timeline[-1][1]
        for candidate, candidate_duration in timeline:
            if t < elapsed + candidate_duration:
                kind = candidate
                local = t - elapsed
                scene_duration = candidate_duration
                break
            elapsed += candidate_duration
        frame = renderer.scene(kind, local, scene_duration).convert("RGB")
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    code = proc.wait()
    if code:
        raise SystemExit(code)
    print(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version", choices=TIMELINES)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    EDIT.mkdir(parents=True, exist_ok=True)
    if args.preview:
        render(args.version, 720, 1280, 25, "-preview")
    else:
        render(args.version, 1080, 1920, 18, "")


if __name__ == "__main__":
    main()
