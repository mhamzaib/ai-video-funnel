"""Shared text helpers for VO cleaning and SFX extraction."""

from __future__ import annotations

import re


SEED_IN_TEXT = re.compile(
    r"\(?\s*seed\s*[=:]?\s*\d+\s*\)?",
    re.IGNORECASE,
)
SFX_BRACKET = re.compile(r"\[([^\]]+)\]")
PAREN = re.compile(r"\([^)]*\)")


def extract_sfx(text: str) -> tuple[str, str]:
    """Return (clean_voiceover, combined_sfx_labels)."""
    labels = [m.group(1).strip() for m in SFX_BRACKET.finditer(text)]
    cleaned = SFX_BRACKET.sub("", text)
    cleaned = SEED_IN_TEXT.sub("", cleaned)
    cleaned = PAREN.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .,;")
    return cleaned, ", ".join(labels)


def clean_for_tts(text: str) -> str:
    cleaned, _ = extract_sfx(text)
    # Keep natural sentence rhythm; do not inject fake "..." drama
    return cleaned.strip()


def strip_seed_mentions(text: str) -> str:
    return SEED_IN_TEXT.sub("", text).strip()
