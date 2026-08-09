"""Viral YouTube Shorts metadata generation via OpenAI."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from core.openai_client import get_openai_client
from core.schemas import EpisodeScript, SeriesPack, VideoMetadata, render_template
from core.series_loader import episode_dir, load_series

logger = logging.getLogger(__name__)


def generate_metadata(
    slug: str,
    episode: int,
    *,
    pack: Optional[SeriesPack] = None,
    script: Optional[EpisodeScript] = None,
) -> VideoMetadata:
    from core.brain import load_episode_script

    pack = pack or load_series(slug)
    script = script or load_episode_script(slug, episode)

    system = pack.prompts.get("metadata_system")
    if not system:
        raise FileNotFoundError(
            f"Pack {slug} missing prompts/metadata_system.md"
        )

    keywords = ", ".join(pack.config.seo_keywords) or pack.config.genre
    user = render_template(
        """Create metadata for episode {{episode}} of "{{series_name}}".
Genre: {{genre}}
Keywords: {{keywords}}
Episode title: {{episode_title}}
Hook: {{hook}}
Cliffhanger: {{cliffhanger}}
Summary (do not spoil fully): {{summary}}

Return JSON:
{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "hashtags": ["#Shorts", "..."]
}
""",
        {
            "episode": episode,
            "series_name": pack.config.name,
            "genre": pack.config.genre,
            "keywords": keywords,
            "episode_title": script.episode_title,
            "hook": script.hook or script.episode_title,
            "cliffhanger": script.cliffhanger,
            "summary": script.episode_summary,
        },
    )

    response = get_openai_client().chat.completions.create(
        model=pack.config.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    data = json.loads(re.sub(r"```json|```", "", raw).strip())
    meta = VideoMetadata.model_validate(data)

    # Enforce product rules
    if len(meta.title) > 100:
        meta.title = meta.title[:97] + "..."
    if "#Shorts" not in meta.description and "shorts" not in meta.description.lower():
        meta.description = meta.description.rstrip() + "\n\n#Shorts"
    if "#Shorts" not in meta.hashtags:
        meta.hashtags = ["#Shorts", *meta.hashtags]
    brand = pack.config.name
    if brand.lower() not in meta.description.lower():
        meta.description = f"{meta.description.rstrip()}\n\n{brand} — Episode {episode}"

    ep = episode_dir(slug, episode)
    ep.mkdir(parents=True, exist_ok=True)
    out = ep / "metadata.json"
    out.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Wrote metadata %s", out)
    return meta


def load_metadata(slug: str, episode: int) -> VideoMetadata:
    path = episode_dir(slug, episode) / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"No metadata.json at {path}")
    return VideoMetadata.model_validate_json(path.read_text(encoding="utf-8"))
