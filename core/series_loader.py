"""Load and persist series packs from series/<slug>/."""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Optional

import yaml

from core.schemas import Character, Progress, SeriesConfig, SeriesPack

ROOT = Path(__file__).resolve().parent.parent
SERIES_DIR = ROOT / "series"
TEMPLATES_DIR = ROOT / "templates" / "series"


def series_root(slug: str) -> Path:
    return SERIES_DIR / slug


def episode_dir(slug: str, episode: int) -> Path:
    return series_root(slug) / "output" / "episodes" / f"{episode:03d}"


def ensure_episode_dirs(slug: str, episode: int) -> Path:
    ep = episode_dir(slug, episode)
    (ep / "audio").mkdir(parents=True, exist_ok=True)
    (ep / "video").mkdir(parents=True, exist_ok=True)
    return ep


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required pack file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def load_prompts(pack_root: Path) -> dict[str, str]:
    prompts_dir = pack_root / "prompts"
    prompts: dict[str, str] = {}
    if not prompts_dir.exists():
        return prompts
    for path in prompts_dir.glob("*.md"):
        prompts[path.stem] = path.read_text(encoding="utf-8")
    return prompts


def load_series(slug: str) -> SeriesPack:
    root = series_root(slug)
    if not root.exists():
        raise FileNotFoundError(
            f"Series pack not found: {root}. "
            f"Create one with: python main.py init --slug {slug} --template analog_horror"
        )

    raw_config = _load_yaml(root / "series.yaml")
    raw_config.setdefault("slug", slug)
    config = SeriesConfig.model_validate(raw_config)

    raw_chars = _load_yaml(root / "characters.yaml")
    char_list = raw_chars.get("characters", raw_chars if isinstance(raw_chars, list) else [])
    characters = [Character.model_validate(c) for c in char_list]
    if not characters:
        raise ValueError(f"No characters in {root / 'characters.yaml'}")

    progress_path = root / "progress.json"
    if progress_path.exists():
        progress = Progress.model_validate(
            json.loads(progress_path.read_text(encoding="utf-8-sig"))
        )
    else:
        progress = Progress()

    world_bible = _read_text(root / "world_bible.md").strip()
    prompts = load_prompts(root)

    return SeriesPack(
        root=str(root),
        config=config,
        characters=characters,
        progress=progress,
        world_bible=world_bible,
        prompts=prompts,
    )


def save_progress(pack: SeriesPack) -> None:
    path = Path(pack.root) / "progress.json"
    path.write_text(
        pack.progress.model_dump_json(indent=2),
        encoding="utf-8",
    )


def save_series_status(slug: str, status: str) -> SeriesPack:
    pack = load_series(slug)
    raw = _load_yaml(Path(pack.root) / "series.yaml")
    raw["status"] = status
    (Path(pack.root) / "series.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return load_series(slug)


def list_templates() -> list[str]:
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir())


def init_series(
    slug: str,
    template: str,
    name: Optional[str] = None,
    overwrite: bool = False,
) -> Path:
    templates = list_templates()
    if template not in templates:
        raise ValueError(
            f"Unknown template '{template}'. Available: {', '.join(templates) or '(none)'}"
        )

    dest = series_root(slug)
    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"Series already exists at {dest}. Pass overwrite=True to replace."
        )
    if dest.exists() and overwrite:
        shutil.rmtree(dest)

    src = TEMPLATES_DIR / template
    shutil.copytree(src, dest)

    # Patch series.yaml slug/name and ensure seeds
    series_path = dest / "series.yaml"
    raw = _load_yaml(series_path)
    raw["slug"] = slug
    raw["name"] = name or slug.replace("_", " ").title()
    series_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    chars_path = dest / "characters.yaml"
    chars_raw = _load_yaml(chars_path)
    characters = chars_raw.get("characters", [])
    for char in characters:
        if not char.get("visual_seed"):
            char["visual_seed"] = random.randint(1_000_000, 9_999_999)
    chars_path.write_text(
        yaml.safe_dump({"characters": characters}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    progress_path = dest / "progress.json"
    if not progress_path.exists():
        progress_path.write_text(
            Progress(
                current_episode=1,
                current_status="Pilot episode — begin the story.",
            ).model_dump_json(indent=2),
            encoding="utf-8",
        )

    (dest / "output" / "episodes").mkdir(parents=True, exist_ok=True)
    return dest
