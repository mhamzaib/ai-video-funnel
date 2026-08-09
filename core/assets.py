"""TTS + Flux still generation driven by series pack config."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import fal_client
import requests
import yaml
from dotenv import load_dotenv

from core.brain import load_episode_script
from core.openai_client import get_openai_client
from core.schemas import EpisodeScript, SeriesPack
from core.series_loader import ensure_episode_dirs, load_series
from core.text_utils import clean_for_tts

load_dotenv()
logger = logging.getLogger(__name__)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_tts_chunks(text: str) -> list[str]:
    cleaned = clean_for_tts(text)
    parts = [p.strip() for p in SENTENCE_SPLIT.split(cleaned) if p.strip()]
    return parts or [cleaned]


def _chunk_instruction(
    base: str,
    delivery: str,
    index: int,
    total: int,
) -> str:
    role = "opening line"
    if total == 1:
        role = "single line"
    elif index == 0:
        role = "setup — measured"
    elif index == total - 1:
        role = "landing — lean in slightly, then stop clean"
    else:
        role = "middle — keep momentum, avoid flatness"

    return (
        f"{base}\n"
        f"Scene delivery: {delivery}\n"
        f"This is chunk {index + 1} of {total} ({role}). "
        f"Vary pitch and timing naturally. Do not sound like a GPS or audiobook robot. "
        f"Breathe at commas. Do not rush. Do not pad with fake drama."
    )


def _ffmpeg_concat_mp3(parts: list[Path], out_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        # Fallback: write first chunk only if somehow ffmpeg missing mid-run
        shutil.copy2(parts[0], out_path)
        return
    with tempfile.TemporaryDirectory(prefix="tts_concat_") as tmp:
        tmp_path = Path(tmp)
        listing = tmp_path / "list.txt"
        local_names = []
        for i, src in enumerate(parts):
            local = tmp_path / f"p{i:02d}.mp3"
            shutil.copy2(src, local)
            local_names.append(local.name)
        listing.write_text(
            "\n".join(f"file '{name}'" for name in local_names),
            encoding="utf-8",
        )
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(tmp_path))
        if result.returncode != 0:
            # re-encode join if copy fails
            cmd[-3:-1] = ["-c:a", "aac"]  # wrong for mp3
            cmd = [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(out_path),
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(tmp_path)
            )
            if result.returncode != 0:
                raise RuntimeError(f"Audio concat failed: {result.stderr[-1500:]}")


def generate_voiceover(
    pack: SeriesPack,
    scene_id: int,
    text: str,
    out_path: Path,
    *,
    delivery: str = "",
    voice_id: Optional[str] = None,
) -> Path:
    """Generate expressive VO by recording sentence chunks with delivery notes."""
    protagonist = pack.protagonist()
    cfg = pack.config
    voice = voice_id or protagonist.voice_id or cfg.default_voice_id
    model = cfg.tts_model or "gpt-4o-mini-tts"
    base_instructions = (cfg.voice_instructions or "").strip()
    scene_delivery = (delivery or "").strip() or (
        "Measured, close-mic. Vary pace. Pause before the last image."
    )
    chunks = _split_tts_chunks(text)
    logger.info(
        "TTS scene %s model=%s voice=%s chunks=%s",
        scene_id,
        model,
        voice,
        len(chunks),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    client = get_openai_client()

    with tempfile.TemporaryDirectory(prefix=f"tts_s{scene_id}_") as tmp:
        tmp_path = Path(tmp)
        part_paths: list[Path] = []
        for i, chunk in enumerate(chunks):
            part = tmp_path / f"chunk_{i:02d}.mp3"
            last_err: Optional[Exception] = None
            for attempt in range(3):
                try:
                    kwargs: dict = {
                        "model": model,
                        "voice": voice,
                        "input": chunk,
                    }
                    if "tts-1" not in model:
                        kwargs["instructions"] = _chunk_instruction(
                            base_instructions, scene_delivery, i, len(chunks)
                        )
                    response = client.audio.speech.create(**kwargs)
                    response.write_to_file(str(part))
                    part_paths.append(part)
                    last_err = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    logger.warning(
                        "TTS scene %s chunk %s attempt %s failed: %s",
                        scene_id,
                        i,
                        attempt + 1,
                        exc,
                    )
                    time.sleep(1.2 * (attempt + 1))
            if last_err:
                raise RuntimeError(
                    f"TTS failed for scene {scene_id} chunk {i}: {last_err}"
                )

        if len(part_paths) == 1:
            shutil.copy2(part_paths[0], out_path)
        else:
            _ffmpeg_concat_mp3(part_paths, out_path)
    return out_path


def _reference_path(pack: SeriesPack) -> Path:
    char = pack.protagonist()
    rel = char.reference_image or f"assets/{char.name.lower()}_ref.jpg"
    return Path(pack.root) / rel


def ensure_character_reference(pack: SeriesPack) -> Path:
    """Create a locked bust portrait once, save into the series pack."""
    ref = _reference_path(pack)
    if ref.exists() and ref.stat().st_size > 1000:
        return ref

    char = pack.protagonist()
    cfg = pack.config
    ref.parent.mkdir(parents=True, exist_ok=True)
    prompt = (
        f"Character reference sheet portrait of {char.name}: {char.appearance}. "
        f"Front-facing bust, neutral industrial backdrop, clear face, "
        f"identical costume details, {cfg.style_prompt}"
    )
    logger.info("Generating character reference for %s -> %s", char.name, ref)
    handler = fal_client.submit(
        cfg.image_model,
        arguments={
            "prompt": prompt,
            "image_size": "square_hd",
            "num_inference_steps": max(cfg.image_steps, 4),
            "seed": char.visual_seed,
            "enable_safety_checker": True,
        },
    )
    result = handler.get()
    url = result["images"][0]["url"]
    ref.write_bytes(requests.get(url, timeout=120).content)

    # Persist path onto characters.yaml if missing
    chars_path = Path(pack.root) / "characters.yaml"
    raw = yaml.safe_load(chars_path.read_text(encoding="utf-8-sig")) or {}
    characters = raw.get("characters", [])
    for item in characters:
        if item.get("name") == char.name and not item.get("reference_image"):
            item["reference_image"] = str(ref.relative_to(pack.root)).replace("\\", "/")
    chars_path.write_text(
        yaml.safe_dump({"characters": characters}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return ref


def generate_still(
    pack: SeriesPack,
    scene_id: int,
    prompt: str,
    out_path: Path,
) -> Path:
    protagonist = pack.protagonist()
    seed = protagonist.visual_seed
    cfg = pack.config
    out_path.parent.mkdir(parents=True, exist_ok=True)

    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            if cfg.use_character_ref:
                ref = ensure_character_reference(pack)
                ref_url = fal_client.upload_file(str(ref))
                logger.info(
                    "PuLID still scene %s seed=%s ref=%s",
                    scene_id,
                    seed,
                    ref.name,
                )
                handler = fal_client.submit(
                    cfg.identity_model,
                    arguments={
                        "prompt": prompt,
                        "reference_image_url": ref_url,
                        "image_size": cfg.image_size,
                        "num_inference_steps": cfg.identity_steps,
                        "seed": seed,
                        "id_weight": cfg.id_weight,
                        "enable_safety_checker": True,
                        "negative_prompt": (
                            "bad quality, worst quality, deformed face, extra limbs, "
                            "different person, child, comic speech bubble, text, watermark"
                        ),
                    },
                )
            else:
                logger.info("Flux still scene %s seed=%s", scene_id, seed)
                handler = fal_client.submit(
                    cfg.image_model,
                    arguments={
                        "prompt": prompt,
                        "image_size": cfg.image_size,
                        "num_inference_steps": cfg.image_steps,
                        "seed": seed,
                        "enable_safety_checker": True,
                    },
                )
            result = handler.get()
            image_url = result["images"][0]["url"]
            response = requests.get(image_url, timeout=120)
            response.raise_for_status()
            out_path.write_bytes(response.content)
            return out_path
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("Image attempt %s failed: %s", attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Image generation failed for scene {scene_id}: {last_err}")


def process_all_assets(
    slug: str,
    episode: int,
    *,
    pack: Optional[SeriesPack] = None,
    script: Optional[EpisodeScript] = None,
    regen_scene: Optional[int] = None,
    audio_only: bool = False,
    images_only: bool = False,
) -> dict:
    pack = pack or load_series(slug)
    script = script or load_episode_script(slug, episode)
    ep_dir = ensure_episode_dirs(slug, episode)
    audio_dir = ep_dir / "audio"
    video_dir = ep_dir / "video"

    if pack.config.use_character_ref and not images_only:
        # Warm ref early even on audio_only skipped — only when generating images
        pass
    if pack.config.use_character_ref and not audio_only:
        ensure_character_reference(pack)

    items = []
    failures = []

    for scene in script.scenes:
        audio_path = audio_dir / f"audio_{scene.id}.mp3"
        image_path = video_dir / f"image_{scene.id}.jpg"

        if regen_scene is not None and scene.id != regen_scene:
            if not audio_path.exists() or not image_path.exists():
                failures.append(
                    {
                        "id": scene.id,
                        "error": "Missing existing media while regenerating another scene",
                    }
                )
                continue
            items.append(
                {
                    "id": scene.id,
                    "audio": str(audio_path),
                    "image": str(image_path),
                    "voiceover": scene.voiceover,
                    "sfx": scene.sfx,
                    "delivery": scene.delivery,
                }
            )
            continue

        try:
            if not images_only:
                generate_voiceover(
                    pack,
                    scene.id,
                    scene.voiceover,
                    audio_path,
                    delivery=scene.delivery,
                )
            elif not audio_path.exists():
                raise FileNotFoundError(f"Missing audio for scene {scene.id}")

            if not audio_only:
                generate_still(pack, scene.id, scene.visual_prompt, image_path)
            elif not image_path.exists():
                raise FileNotFoundError(f"Missing image for scene {scene.id}")

            items.append(
                {
                    "id": scene.id,
                    "audio": str(audio_path),
                    "image": str(image_path),
                    "voiceover": scene.voiceover,
                    "sfx": scene.sfx,
                    "delivery": scene.delivery,
                }
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": scene.id, "error": str(exc)})
            logger.error("Scene %s asset failure: %s", scene.id, exc)

    manifest = {
        "series": slug,
        "episode": episode,
        "episode_title": script.episode_title,
        "scenes": items,
        "failures": failures,
    }
    manifest_path = ep_dir / "assets_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if failures:
        raise RuntimeError(
            f"Asset generation incomplete ({len(failures)} scenes failed). "
            f"See {manifest_path}"
        )

    logger.info("Assets ready: %s (%s scenes)", manifest_path, len(items))
    return manifest


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    if len(sys.argv) < 3:
        raise SystemExit("Usage: python -m core.assets <series_slug> <episode>")
    process_all_assets(sys.argv[1], int(sys.argv[2]))
