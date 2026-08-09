"""Pydantic schemas for series packs, scripts, and SEO metadata."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Character(BaseModel):
    name: str
    appearance: str = Field(
        description="Locked visual description used on every image prompt"
    )
    visual_seed: int
    voice_id: str = "ash"
    voice_speed: float = 1.0
    role: str = "protagonist"
    reference_image: Optional[str] = None  # relative path inside series pack
    pronouns: str = "he/him"  # used by writing prompts


class CaptionStyle(BaseModel):
    font: str = "Arial"
    font_size: int = 48
    primary_color: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    outline: int = 3
    margin_v: int = 120


class SeriesConfig(BaseModel):
    name: str
    slug: str
    genre: str
    style_prompt: str
    image_size: str = "portrait_16_9"
    image_model: str = "fal-ai/flux/schnell"
    identity_model: str = "fal-ai/flux-pulid"
    image_steps: int = 4
    identity_steps: int = 20
    id_weight: float = 0.9
    use_character_ref: bool = True
    llm_model: str = "gpt-4o-mini"
    scenes_per_episode: int = 6
    plot_history_limit: int = 8
    tts_model: str = "gpt-4o-mini-tts"
    default_voice_id: str = "ash"
    default_voice_speed: float = 1.0
    voice_instructions: str = (
        "Speak like a documentary narrator discovering something wrong. "
        "Natural pacing, quiet tension, slight variation in emphasis. "
        "Not monotone. Not theatrical. Not cheerful. Close-mic, cinematic."
    )
    privacy_status: str = "unlisted"
    made_for_kids: bool = False
    youtube_category_id: str = "24"
    seo_keywords: list[str] = Field(default_factory=list)
    caption: CaptionStyle = Field(default_factory=CaptionStyle)
    status: str = "active"  # active | archived | complete


class PlotBeat(BaseModel):
    episode: int
    summary: str
    cliffhanger: str = ""


class EpisodeUpload(BaseModel):
    episode: int
    youtube_video_id: Optional[str] = None
    title: Optional[str] = None


class Progress(BaseModel):
    current_episode: int = 1
    current_status: str = ""
    plot_history: list[PlotBeat] = Field(default_factory=list)
    uploads: list[EpisodeUpload] = Field(default_factory=list)
    last_youtube_video_id: Optional[str] = None

    def history_for_prompt(self, limit: int) -> str:
        if not self.plot_history:
            return "(No previous episodes yet — this is the start of the series.)"
        beats = self.plot_history[-limit:]
        lines = []
        for beat in beats:
            ch = f" Cliffhanger: {beat.cliffhanger}" if beat.cliffhanger else ""
            lines.append(f"Episode {beat.episode}: {beat.summary}{ch}")
        return "\n".join(lines)


class SceneScript(BaseModel):
    id: int
    voiceover: str
    visual_prompt: str
    duration: float = 5.0
    sfx: str = ""
    delivery: str = (
        "Measured, close-mic. Vary pace. Pause before the last image."
    )

    @field_validator("voiceover")
    @classmethod
    def no_seed_in_voiceover(cls, value: str) -> str:
        return value.strip()


class EpisodeScript(BaseModel):
    episode_title: str
    hook: str = ""
    scenes: list[SceneScript]
    episode_summary: str
    next_status: str
    cliffhanger: str = ""

    @field_validator("scenes")
    @classmethod
    def scenes_nonempty(cls, value: list[SceneScript]) -> list[SceneScript]:
        if not value:
            raise ValueError("Episode must have at least one scene")
        return value


class VideoMetadata(BaseModel):
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)


class SeriesPack(BaseModel):
    """Loaded pack: config + characters + progress + rendered prompt paths."""

    root: str
    config: SeriesConfig
    characters: list[Character]
    progress: Progress
    world_bible: str
    prompts: dict[str, str] = Field(default_factory=dict)

    def protagonist(self) -> Character:
        for char in self.characters:
            if char.role == "protagonist":
                return char
        if not self.characters:
            raise ValueError(f"No characters defined for series {self.config.slug}")
        return self.characters[0]

    def character_lock_block(self) -> str:
        lines = [
            "CHARACTER LOCK (identical every frame - same face, hair, clothing, age):"
        ]
        for char in self.characters:
            lines.append(f"- {char.name}: {char.appearance}")
        lines.append(
            "Do not redesign, recolor, or age characters. Keep outfits identical."
        )
        return "\n".join(lines)

    def characters_for_prompt(self) -> str:
        lines = []
        for char in self.characters:
            lines.append(
                f"- {char.name} ({char.role}, {char.pronouns}): {char.appearance} "
                f"[voice={char.voice_id}, visual_seed_api_only={char.visual_seed}]"
            )
        return "\n".join(lines)

    model_config = {"arbitrary_types_allowed": True}


def render_template(template: str, values: dict[str, Any]) -> str:
    """Replace {{key}} placeholders. Unknown keys left intact."""
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result
