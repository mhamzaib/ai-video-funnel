"""CLI orchestrator for the multi-series AI video funnel."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.series_loader import (
    ROOT,
    init_series,
    list_templates,
    load_series,
    save_series_status,
    series_root,
)

DEFAULT_STAGES = ["brain", "assets", "compile", "seo", "upload"]


def _setup_logging(slug: Optional[str]) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if slug:
        log_dir = series_root(slug) / "output"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def _resolve_episode(slug: str, explicit: Optional[int], stages: list[str]) -> int:
    pack = load_series(slug)
    if explicit is not None:
        return explicit
    if "brain" in stages:
        return pack.progress.current_episode
    # Prefer last written episode folder with a script
    episodes_root = series_root(slug) / "output" / "episodes"
    if episodes_root.exists():
        candidates = sorted(
            [
                p
                for p in episodes_root.iterdir()
                if p.is_dir() and (p / "script.json").exists()
            ],
            reverse=True,
        )
        if candidates:
            return int(candidates[0].name)
    # Fallback after memory advanced
    return max(pack.progress.current_episode - 1, 1)


def cmd_init(args: argparse.Namespace) -> None:
    dest = init_series(
        slug=args.slug,
        template=args.template,
        name=args.name,
        overwrite=args.overwrite,
    )
    print(f"Created series pack at {dest}")
    print("Edit series.yaml, characters.yaml, and world_bible.md before running.")


def cmd_status(args: argparse.Namespace) -> None:
    pack = load_series(args.series)
    cfg = pack.config
    prog = pack.progress
    print(f"Series: {cfg.name} ({cfg.slug})")
    print(f"Status: {cfg.status} | Genre: {cfg.genre}")
    print(f"Next episode to generate: {prog.current_episode}")
    print(f"Current status beat: {prog.current_status}")
    print(f"Plot beats stored: {len(prog.plot_history)}")
    if prog.plot_history:
        last = prog.plot_history[-1]
        print(f"Last beat E{last.episode}: {last.summary}")
    print(f"Last YouTube id: {prog.last_youtube_video_id or '(none)'}")

    ep_root = series_root(args.series) / "output" / "episodes"
    if ep_root.exists():
        print("Episode artifacts:")
        for folder in sorted(ep_root.iterdir()):
            if not folder.is_dir():
                continue
            flags = []
            for name in (
                "script.json",
                "assets_manifest.json",
                "final.mp4",
                "metadata.json",
                "youtube_video_id.txt",
            ):
                if (folder / name).exists():
                    flags.append(name.split(".")[0])
            print(f"  {folder.name}: {', '.join(flags) or '(empty)'}")


def cmd_archive(args: argparse.Namespace) -> None:
    status = "complete" if args.complete else "archived"
    save_series_status(args.series, status)
    print(f"Series {args.series} marked {status}")


def cmd_activate(args: argparse.Namespace) -> None:
    save_series_status(args.series, "active")
    print(f"Series {args.series} marked active")


def cmd_run(args: argparse.Namespace) -> None:
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stages if s not in DEFAULT_STAGES]
    if unknown:
        raise SystemExit(f"Unknown stages: {unknown}. Allowed: {DEFAULT_STAGES}")

    _setup_logging(args.series)
    log = logging.getLogger("main")

    pack = load_series(args.series)
    if pack.config.status in {"archived", "complete"} and not args.force:
        raise SystemExit(
            f"Series is {pack.config.status}. Pass --force or run: "
            f"python main.py activate --series {args.series}"
        )

    episode = _resolve_episode(args.series, args.episode, stages)
    script = None

    if "brain" in stages:
        from core.brain import get_next_episode

        # Capture episode before memory advances
        episode = pack.progress.current_episode if args.episode is None else args.episode
        # If user forced a specific episode number while brain runs, we still use
        # progress.current_episode for generation (story continuity).
        if args.episode is not None and args.episode != pack.progress.current_episode:
            log.warning(
                "Ignoring --episode %s for brain; generating progress episode %s",
                args.episode,
                pack.progress.current_episode,
            )
            episode = pack.progress.current_episode

        script, episode = get_next_episode(
            args.series,
            pack=pack,
            persist=True,
            update_memory=True,
            allow_inactive=args.force,
        )
        log.info("Brain complete: episode %s — %s", episode, script.episode_title)

        if args.review_script:
            path = (
                series_root(args.series)
                / "output"
                / "episodes"
                / f"{episode:03d}"
                / "script.json"
            )
            input(f"Review/edit script at {path} then press Enter to continue...")

    if "assets" in stages:
        from core.assets import process_all_assets

        process_all_assets(
            args.series,
            episode,
            regen_scene=args.regen_scene,
            audio_only=args.audio_only,
            images_only=args.images_only,
        )
        log.info("Assets complete for episode %s", episode)

    if "compile" in stages:
        from core.compiler import compile_episode

        final = compile_episode(args.series, episode)
        log.info("Compile complete: %s", final)

    if "seo" in stages:
        from core.seo import generate_metadata

        meta = generate_metadata(args.series, episode)
        log.info("SEO title: %s", meta.title)

    if "upload" in stages:
        from core.uploader import upload_episode

        video_id = upload_episode(
            args.series,
            episode,
            dry_run=args.dry_run,
            force=args.force_upload,
        )
        if args.dry_run:
            log.info("Upload dry-run complete (no YouTube call)")
        else:
            log.info("Upload complete: %s", video_id)

    log.info("Done. Series=%s episode=%s stages=%s", args.series, episode, stages)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-series AI video funnel (story -> Short -> YouTube)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a series pack from a template")
    p_init.add_argument("--slug", required=True)
    p_init.add_argument("--template", required=True, help=f"One of: {list_templates()}")
    p_init.add_argument("--name", default=None)
    p_init.add_argument("--overwrite", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="Run pipeline stages for a series")
    p_run.add_argument("--series", required=True)
    p_run.add_argument(
        "--stages",
        default=",".join(DEFAULT_STAGES),
        help=f"Comma list from {DEFAULT_STAGES}",
    )
    p_run.add_argument("--episode", type=int, default=None)
    p_run.add_argument("--regen-scene", type=int, default=None)
    p_run.add_argument(
        "--audio-only",
        action="store_true",
        help="During assets stage, regenerate TTS only (keep existing stills)",
    )
    p_run.add_argument(
        "--images-only",
        action="store_true",
        help="During assets stage, regenerate stills only (keep existing audio)",
    )
    p_run.add_argument("--review-script", action="store_true")
    p_run.add_argument("--dry-run", action="store_true", help="Skip real YouTube upload")
    p_run.add_argument("--force", action="store_true", help="Allow archived/complete series")
    p_run.add_argument(
        "--force-upload",
        action="store_true",
        help="Re-upload even if youtube id exists",
    )
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Show series progress and artifacts")
    p_status.add_argument("--series", required=True)
    p_status.set_defaults(func=cmd_status)

    p_arch = sub.add_parser("archive", help="Mark series archived or complete")
    p_arch.add_argument("--series", required=True)
    p_arch.add_argument(
        "--complete",
        action="store_true",
        help="Mark complete instead of archived",
    )
    p_arch.set_defaults(func=cmd_archive)

    p_act = sub.add_parser("activate", help="Reactivate an archived/complete series")
    p_act.add_argument("--series", required=True)
    p_act.set_defaults(func=cmd_activate)

    p_list = sub.add_parser("templates", help="List available series templates")
    p_list.set_defaults(
        func=lambda _a: print("\n".join(list_templates()) or "(no templates)")
    )

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    # Ensure project root is on sys.path when running as script
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
