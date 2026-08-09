"""Optional FFmpeg smoke test — skipped if ffmpeg is unavailable."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.compiler import compile_episode
from core.series_loader import ROOT, ensure_episode_dirs


def _ffmpeg_ok() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(_ffmpeg_ok(), "ffmpeg/ffprobe not on PATH")
class CompilerSmokeTests(unittest.TestCase):
    def test_compile_two_fake_scenes(self):
        slug = "void_signal"
        episode = 999
        ep = ensure_episode_dirs(slug, episode)
        audio_dir = ep / "audio"
        video_dir = ep / "video"

        # Generate tiny fixtures with ffmpeg
        for i in (1, 2):
            img = video_dir / f"image_{i}.jpg"
            aud = audio_dir / f"audio_{i}.mp3"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=gray:s=1080x1920:d=1",
                    "-frames:v",
                    "1",
                    str(img),
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=1",
                    str(aud),
                ],
                check=True,
                capture_output=True,
            )

        manifest = {
            "series": slug,
            "episode": episode,
            "episode_title": "Smoke",
            "scenes": [
                {
                    "id": 1,
                    "audio": str(audio_dir / "audio_1.mp3"),
                    "image": str(video_dir / "image_1.jpg"),
                    "voiceover": "Smoke test one.",
                    "sfx": "",
                },
                {
                    "id": 2,
                    "audio": str(audio_dir / "audio_2.mp3"),
                    "image": str(video_dir / "image_2.jpg"),
                    "voiceover": "Smoke test two.",
                    "sfx": "",
                },
            ],
            "failures": [],
        }
        (ep / "assets_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        final = compile_episode(slug, episode)
        self.assertTrue(final.exists())
        self.assertGreater(final.stat().st_size, 1000)

        # Cleanup smoke episode artifacts
        shutil.rmtree(ep)


if __name__ == "__main__":
    unittest.main()
