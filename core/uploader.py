"""YouTube Shorts upload via Data API v3."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from core.schemas import EpisodeUpload, SeriesPack, VideoMetadata
from core.series_loader import episode_dir, load_series, save_progress
from core.seo import generate_metadata, load_metadata

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _secrets_path() -> Path:
    return Path(os.getenv("YOUTUBE_CLIENT_SECRETS", "secrets/youtube_client_secrets.json"))


def _token_path() -> Path:
    return Path(os.getenv("YOUTUBE_TOKEN", "secrets/youtube_token.json"))


def get_youtube_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google API packages missing. pip install -r requirements.txt"
        ) from exc

    secrets = _secrets_path()
    token = _token_path()
    if not secrets.exists():
        raise FileNotFoundError(
            f"YouTube client secrets not found at {secrets}. "
            "Download OAuth client JSON from Google Cloud Console."
        )

    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
            creds = flow.run_local_server(port=0)
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def upload_episode(
    slug: str,
    episode: int,
    *,
    pack: Optional[SeriesPack] = None,
    dry_run: bool = False,
    force: bool = False,
) -> Optional[str]:
    pack = pack or load_series(slug)
    ep = episode_dir(slug, episode)
    video_path = ep / "final.mp4"
    if not video_path.exists():
        raise FileNotFoundError(f"Missing final.mp4 at {video_path}. Run compile first.")

    # Skip if already uploaded
    existing = next(
        (u for u in pack.progress.uploads if u.episode == episode and u.youtube_video_id),
        None,
    )
    if existing and not force:
        logger.info(
            "Episode %s already uploaded as %s — skip (use --force)",
            episode,
            existing.youtube_video_id,
        )
        return existing.youtube_video_id

    try:
        meta = load_metadata(slug, episode)
    except FileNotFoundError:
        meta = generate_metadata(slug, episode, pack=pack)

    if dry_run:
        logger.info(
            "DRY RUN upload: title=%r path=%s privacy=%s",
            meta.title,
            video_path,
            pack.config.privacy_status,
        )
        (ep / "upload_dry_run.json").write_text(
            meta.model_dump_json(indent=2), encoding="utf-8"
        )
        return None

    from googleapiclient.http import MediaFileUpload

    youtube = get_youtube_service()
    body = {
        "snippet": {
            "title": meta.title,
            "description": meta.description,
            "tags": meta.tags,
            "categoryId": pack.config.youtube_category_id,
        },
        "status": {
            "privacyStatus": pack.config.privacy_status,
            "selfDeclaredMadeForKids": pack.config.made_for_kids,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("Upload progress %.1f%%", status.progress() * 100)

    video_id = response["id"]
    logger.info("Uploaded YouTube video %s", video_id)

    # Refresh pack progress and record
    pack = load_series(slug)
    pack.progress.uploads = [
        u for u in pack.progress.uploads if u.episode != episode
    ]
    pack.progress.uploads.append(
        EpisodeUpload(episode=episode, youtube_video_id=video_id, title=meta.title)
    )
    pack.progress.last_youtube_video_id = video_id
    save_progress(pack)
    (ep / "youtube_video_id.txt").write_text(video_id, encoding="utf-8")
    return video_id
