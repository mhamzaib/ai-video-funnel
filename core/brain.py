"""Episode script generation via OpenAI using series pack prompts."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from core.openai_client import get_openai_client
from core.schemas import (
    EpisodeScript,
    PlotBeat,
    SeriesPack,
    render_template,
)
from core.series_loader import ensure_episode_dirs, load_series, save_progress
from core.text_utils import extract_sfx, strip_seed_mentions

logger = logging.getLogger(__name__)


def _build_prompt_values(pack: SeriesPack) -> dict:
    cfg = pack.config
    lead = pack.protagonist()
    is_pilot = (
        pack.progress.current_episode <= 1 and not pack.progress.plot_history
    )
    if is_pilot:
        episode_mode = "PILOT"
        pilot_brief = (
            "SERIES PILOT. Introduce the lead with economy — one clean naming, "
            "then pronouns. Establish world rule + first anomaly. No mid-arc language."
        )
        current_status = (
            "SERIES START. Viewer knows nothing. Open as a prologue, not a continuation."
        )
        plot_history = (
            "(No previous episodes. Episode 1 — cold-open prologue + first hunt.)"
        )
    else:
        episode_mode = "CONTINUATION"
        pilot_brief = (
            "Continuation. Do not restart the origin. Advance the arc."
        )
        current_status = pack.progress.current_status or "(Continue the arc.)"
        plot_history = pack.progress.history_for_prompt(cfg.plot_history_limit)

    return {
        "series_name": cfg.name,
        "genre": cfg.genre,
        "world_bible": pack.world_bible or "(No world bible provided.)",
        "characters": pack.characters_for_prompt(),
        "current_status": current_status,
        "plot_history": plot_history,
        "episode": pack.progress.current_episode,
        "scene_count": cfg.scenes_per_episode,
        "episode_mode": episode_mode,
        "pilot_brief": pilot_brief,
        "pronouns": lead.pronouns,
    }


def assemble_prompts(pack: SeriesPack) -> tuple[str, str]:
    prompts = pack.prompts
    if "narration_system" not in prompts or "episode_user" not in prompts:
        raise FileNotFoundError(
            f"Pack {pack.config.slug} missing prompts/narration_system.md "
            f"or prompts/episode_user.md"
        )
    values = _build_prompt_values(pack)
    system = render_template(prompts["narration_system"], values)
    user = render_template(prompts["episode_user"], values)
    return system, user


def _parse_json_content(raw: str) -> dict:
    clean = re.sub(r"```json|```", "", raw or "").strip()
    return json.loads(clean)


def apply_character_lock(pack: SeriesPack, script: EpisodeScript) -> EpisodeScript:
    """Append locked appearance + style to every visual prompt; clean VO/SFX."""
    lock = pack.character_lock_block()
    style = pack.config.style_prompt
    for scene in script.scenes:
        vo, sfx_from_vo = extract_sfx(scene.voiceover)
        scene.voiceover = strip_seed_mentions(vo)
        if not scene.sfx and sfx_from_vo:
            scene.sfx = sfx_from_vo
        scene.visual_prompt = strip_seed_mentions(scene.visual_prompt).strip()
        # Avoid duplicating lock if reprocessing
        if "CHARACTER LOCK" not in scene.visual_prompt:
            scene.visual_prompt = (
                f"{scene.visual_prompt}. {lock}. Style: {style}"
            ).strip()
    return script


def _call_llm(pack: SeriesPack, system: str, user: str) -> EpisodeScript:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=pack.config.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    data = _parse_json_content(raw)
    script = EpisodeScript.model_validate(data)
    if not script.episode_summary.strip() or not script.next_status.strip():
        raise ValueError("Model omitted episode_summary or next_status")
    if len(script.scenes) < 1:
        raise ValueError("Model returned no scenes")
    return apply_character_lock(pack, script)


def get_next_episode(
    slug: str,
    *,
    pack: Optional[SeriesPack] = None,
    persist: bool = True,
    update_memory: bool = True,
    allow_inactive: bool = False,
) -> tuple[EpisodeScript, int]:
    """Generate script for the current episode number.

    Returns (script, episode_number_written). Memory increment happens after
    the script is written so callers can run assets against that episode.
    """
    pack = pack or load_series(slug)
    if pack.config.status in {"archived", "complete"} and not allow_inactive:
        raise RuntimeError(
            f"Series '{slug}' is {pack.config.status}. "
            "Use --force or reactivate the series."
        )

    episode_num = pack.progress.current_episode
    system, user = assemble_prompts(pack)
    last_error: Optional[Exception] = None
    script: Optional[EpisodeScript] = None
    for attempt in range(2):
        try:
            script = _call_llm(pack, system, user)
            break
        except Exception as exc:  # noqa: BLE001 — retry once on schema/LLM failure
            last_error = exc
            logger.warning("Brain attempt %s failed: %s", attempt + 1, exc)
    if script is None:
        raise RuntimeError(f"Failed to generate episode script: {last_error}")

    if persist:
        ep_dir = ensure_episode_dirs(slug, episode_num)
        out_path = ep_dir / "script.json"
        out_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Wrote script to %s", out_path)

    if update_memory:
        update_series_memory(pack, script, episode_num=episode_num)

    return script, episode_num


def update_series_memory(
    pack: SeriesPack,
    script: EpisodeScript,
    *,
    episode_num: Optional[int] = None,
) -> None:
    ep = episode_num if episode_num is not None else pack.progress.current_episode
    # Avoid duplicate history if memory already advanced for this episode
    if any(b.episode == ep for b in pack.progress.plot_history):
        logger.info("Plot history already has episode %s — skipping append", ep)
    else:
        pack.progress.plot_history.append(
            PlotBeat(
                episode=ep,
                summary=script.episode_summary,
                cliffhanger=script.cliffhanger,
            )
        )
    pack.progress.current_status = script.next_status
    if pack.progress.current_episode <= ep:
        pack.progress.current_episode = ep + 1
    save_progress(pack)
    logger.info(
        "Memory updated: next episode will be %s", pack.progress.current_episode
    )


def load_episode_script(slug: str, episode: int) -> EpisodeScript:
    path = (
        Path(load_series(slug).root)
        / "output"
        / "episodes"
        / f"{episode:03d}"
        / "script.json"
    )
    if not path.exists():
        raise FileNotFoundError(f"No script for episode {episode}: {path}")
    return EpisodeScript.model_validate_json(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m core.brain <series_slug>")
    result, ep = get_next_episode(sys.argv[1])
    print(f"Episode {ep}: {result.episode_title}")
    print(result.scenes[0].voiceover)
