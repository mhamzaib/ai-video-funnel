"""FFmpeg Ken Burns stitcher + burned-in captions for 9:16 Shorts."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

from core.schemas import SeriesPack
from core.series_loader import episode_dir, load_series

logger = logging.getLogger(__name__)

TARGET_W = 1080
TARGET_H = 1920
FPS = 30


def _require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "FFmpeg not found on PATH. Install FFmpeg and restart the shell. "
            "Windows: winget install Gyan.FFmpeg"
        )
    return path


def _probe_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 3.0
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    try:
        return max(float(out), 0.5)
    except ValueError:
        return 3.0


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "%%")
    )


def _caption_chunk(voiceover: str, max_chars: int = 42) -> str:
    words = voiceover.split()
    if not words:
        return ""
    line = " ".join(words[:12])
    return textwrap.shorten(line, width=max_chars, placeholder="...")


def _resolve_fontfile(preferred: str) -> Optional[str]:
    """Return a fontfile path ffmpeg drawtext can use on this OS."""
    candidates = []
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates.extend(
        [
            Path(windir) / "Fonts" / "arial.ttf",
            Path(windir) / "Fonts" / "Arial.ttf",
            Path(windir) / "Fonts" / f"{preferred}.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        ]
    )
    for path in candidates:
        if path.exists():
            # ffmpeg wants forward slashes / escaped colon on Windows
            return path.as_posix().replace(":", "\\:")
    return None


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed ({result.returncode}):\n{result.stderr[-2500:]}"
        )


def _build_scene_clip(
    ffmpeg: str,
    image: Path,
    audio: Path,
    out_clip: Path,
    *,
    caption: str,
    caption_font: str,
    font_size: int,
    zoom_direction: int,
) -> None:
    duration = _probe_duration(audio)
    frames = max(int(duration * FPS), FPS)
    # Classic Ken Burns: upscale then slow zoompan (avoids crashy crop→zoompan)
    z_expr = (
        "min(zoom+0.0015,1.3)"
        if zoom_direction % 2 == 0
        else "if(eq(on,1),1.25,max(zoom-0.0015,1.0))"
    )
    vf = (
        f"scale=3000:-1,"
        f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={TARGET_W}x{TARGET_H}:fps={FPS},"
        f"format=yuv420p"
    )

    fontfile = _resolve_fontfile(caption_font)
    cap = _escape_drawtext(caption) if caption else ""
    if cap and fontfile:
        vf = (
            f"{vf},"
            f"drawtext=fontfile='{fontfile}':text='{cap}':fontsize={font_size}:"
            f"fontcolor=white:borderw=3:bordercolor=black:"
            f"x=(w-text_w)/2:y=h-{120}"
        )

    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image),
        "-i",
        str(audio),
        "-vf",
        vf,
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
        str(out_clip),
    ]
    try:
        _run_ffmpeg(cmd)
    except RuntimeError:
        # Retry without captions if drawtext/font fails
        if not cap:
            raise
        logger.warning("Caption filter failed — retrying scene without drawtext")
        cmd_plain = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-i",
            str(audio),
            "-vf",
            (
                f"scale=3000:-1,"
                f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={TARGET_W}x{TARGET_H}:fps={FPS},"
                f"format=yuv420p"
            ),
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            str(out_clip),
        ]
        _run_ffmpeg(cmd_plain)


def compile_episode(
    slug: str,
    episode: int,
    *,
    pack: Optional[SeriesPack] = None,
) -> Path:
    ffmpeg = _require_ffmpeg()
    pack = pack or load_series(slug)
    ep = episode_dir(slug, episode)
    manifest_path = ep / "assets_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing assets_manifest.json for episode {episode}. Run assets stage first."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenes = manifest.get("scenes") or []
    if not scenes:
        raise RuntimeError("Manifest has no scenes to compile")

    caption_cfg = pack.config.caption
    with tempfile.TemporaryDirectory(prefix="funnel_compile_") as tmp:
        tmp_path = Path(tmp)
        clip_paths: list[Path] = []
        for i, scene in enumerate(scenes):
            image = Path(scene["image"])
            audio = Path(scene["audio"])
            if not image.exists() or not audio.exists():
                raise FileNotFoundError(f"Missing media for scene {scene.get('id')}")
            clip = tmp_path / f"clip_{scene['id']:03d}.mp4"
            _build_scene_clip(
                ffmpeg,
                image,
                audio,
                clip,
                caption=_caption_chunk(scene.get("voiceover") or ""),
                caption_font=caption_cfg.font,
                font_size=caption_cfg.font_size,
                zoom_direction=i,
            )
            clip_paths.append(clip)

        concat_list = tmp_path / "concat.txt"
        lines = []
        for i, src in enumerate(clip_paths):
            local = tmp_path / f"local_{i:03d}.mp4"
            shutil.copy2(src, local)
            lines.append(f"file '{local.name}'")
        concat_list.write_text("\n".join(lines), encoding="utf-8")

        final_path = ep / "final.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(final_path),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(tmp_path)
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed:\n{result.stderr[-2000:]}")

    duration = _probe_duration(final_path)
    meta = {"final": str(final_path), "duration_sec": duration}
    (ep / "compile_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Compiled %s (%.1fs)", final_path, duration)
    return final_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    if len(sys.argv) < 3:
        raise SystemExit("Usage: python -m core.compiler <series_slug> <episode>")
    print(compile_episode(sys.argv[1], int(sys.argv[2])))
