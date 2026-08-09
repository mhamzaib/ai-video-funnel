"""Optional helper: open browser OAuth flow and cache YouTube token."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.uploader import get_youtube_service  # noqa: E402


if __name__ == "__main__":
    get_youtube_service()
    print("YouTube OAuth token saved.")
