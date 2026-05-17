import shutil
import subprocess
from pathlib import Path
from typing import List

from config import FONT_INDEX, FONT_PATH, OUTPUT_DIR, VIDEO_HEIGHT, VIDEO_WIDTH
from lyrics.parser import LyricLine

# Text style constants
_CREAM = (255, 245, 195, 255)
_SHADOW = (0, 0, 0, 200)
_MAX_TEXT_WIDTH = int(VIDEO_WIDTH * 0.83)  # ~897px — leaves margin on each side
_LINE_SPACING = 10                          # px between wrapped lines
_TEXT_CENTER_Y = int(VIDEO_HEIGHT * 0.62)  # vertical anchor point (~lower-center)


class FFmpegError(Exception):
    pass


def check_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found — install it with: brew install ffmpeg (macOS) "
            "or sudo apt install ffmpeg (Linux)"
        )


def loop_video(clip_path: Path, target_duration: float, output_path: Path) -> Path:
    """Loop clip to cover target_duration seconds without re-encoding."""
    _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(clip_path),
        "-t", f"{target_duration:.3f}",
        "-c", "copy",
        str(output_path),
    ])
    return output_path


def overlay_lyrics(
    video_path: Path,
    lyrics: List[LyricLine],
    output_path: Path,
    font_size: int = 80,
) -> Path:
    """
    Burn karaoke-style lyrics onto video.
    Uses Pillow to render each lyric line as a transparent PNG with word wrapping,
    then composites them with ffmpeg's overlay filter.
    """
    pngs = _render_lyric_pngs(lyrics, font_size)
    try:
        filter_complex = _build_overlay_filter(lyrics)
        cmd = ["ffmpeg", "-y", "-i", str(video_path)]
        for png in pngs:
            cmd += ["-i", str(png)]
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            str(output_path),
        ]
        _run(cmd)
    finally:
        for png in pngs:
            if png.exists():
                png.unlink()
    return output_path


def _load_font(font_size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT_PATH, font_size, index=FONT_INDEX)
    except Exception:
        try:
            return ImageFont.truetype(FONT_PATH, font_size)
        except Exception:
            return ImageFont.load_default()


def _wrap_text(text: str, font, draw) -> List[str]:
    """Break text into lines that fit within _MAX_TEXT_WIDTH."""
    words = text.split()
    if not words:
        return [text]

    lines: List[str] = []
    current: List[str] = []

    for word in words:
        test = " ".join(current + [word])
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= _MAX_TEXT_WIDTH or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines


def _render_lyric_pngs(lyrics: List[LyricLine], font_size: int) -> List[Path]:
    """Render each lyric line as a full-frame transparent PNG."""
    from PIL import Image, ImageDraw

    font = _load_font(font_size)
    pngs: List[Path] = []

    for i, line in enumerate(lyrics):
        img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        wrapped = _wrap_text(line.text, font, draw)

        # Measure each wrapped line
        line_sizes = []
        for wl in wrapped:
            bbox = draw.textbbox((0, 0), wl, font=font)
            line_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

        block_h = sum(h for _, h in line_sizes) + _LINE_SPACING * (len(wrapped) - 1)
        y = _TEXT_CENTER_Y - block_h // 2

        for wl, (lw, lh) in zip(wrapped, line_sizes):
            x = (VIDEO_WIDTH - lw) // 2
            # Shadow
            draw.text((x + 2, y + 2), wl, font=font, fill=_SHADOW)
            # Cream text
            draw.text((x, y), wl, font=font, fill=_CREAM)
            y += lh + _LINE_SPACING

        png_path = OUTPUT_DIR / f"_lyric_{i:04d}.png"
        img.save(png_path, "PNG")
        pngs.append(png_path)

    return pngs


def _build_overlay_filter(lyrics: List[LyricLine]) -> str:
    """Build filter_complex: scale to 9:16 then chain timed PNG overlays."""
    parts: List[str] = []

    parts.append(
        f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2[scaled]"
    )

    for i, line in enumerate(lyrics):
        in_v = "scaled" if i == 0 else f"v{i - 1}"
        out_v = f"v{i}" if i < len(lyrics) - 1 else "out"
        parts.append(
            f"[{in_v}][{i + 1}:v]overlay=0:0:"
            f"enable='between(t,{line.start:.3f},{line.end:.3f})'[{out_v}]"
        )

    return ";".join(parts)


def _run(cmd: List[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"ffmpeg failed:\n{result.stderr[-2000:]}")
