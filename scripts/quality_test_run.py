"""One-off quality test: FAL stills + Edge TTS + compile (skips broken OpenAI/OpenRouter)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import edge_tts
import fal_client
import requests

from core.compiler import compile_episode
from core.schemas import EpisodeScript
from core.series_loader import ensure_episode_dirs, load_series

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quality_test")

SLUG = "void_signal"
EPISODE = 1


async def gen_tts(text: str, path: Path, voice: str = "en-US-GuyNeural") -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(path))


def gen_still(prompt: str, seed: int, model: str, image_size: str, steps: int, path: Path) -> None:
    handler = fal_client.submit(
        model,
        arguments={
            "prompt": prompt,
            "image_size": image_size,
            "num_inference_steps": steps,
            "seed": seed,
            "enable_safety_checker": True,
        },
    )
    result = handler.get()
    url = result["images"][0]["url"]
    path.write_bytes(requests.get(url, timeout=120).content)


async def main() -> None:
    pack = load_series(SLUG)
    ep = ensure_episode_dirs(SLUG, EPISODE)
    script = EpisodeScript.model_validate_json(
        (ep / "script.json").read_text(encoding="utf-8")
    )
    seed = pack.protagonist().visual_seed
    items = []

    for scene in script.scenes:
        audio = ep / "audio" / f"audio_{scene.id}.mp3"
        image = ep / "video" / f"image_{scene.id}.jpg"
        logger.info("Scene %s TTS...", scene.id)
        await gen_tts(scene.voiceover, audio)
        logger.info("Scene %s Flux...", scene.id)
        gen_still(
            scene.visual_prompt,
            seed,
            pack.config.image_model,
            pack.config.image_size,
            pack.config.image_steps,
            image,
        )
        items.append(
            {
                "id": scene.id,
                "audio": str(audio),
                "image": str(image),
                "voiceover": scene.voiceover,
                "sfx": scene.sfx,
            }
        )

    manifest = {
        "series": SLUG,
        "episode": EPISODE,
        "episode_title": script.episode_title,
        "scenes": items,
        "failures": [],
    }
    (ep / "assets_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    final = compile_episode(SLUG, EPISODE, pack=pack)
    logger.info("DONE %s", final)


if __name__ == "__main__":
    asyncio.run(main())
