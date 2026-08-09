"""Unit tests that do not require network or FFmpeg."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from core.schemas import EpisodeScript, Progress, render_template
from core.series_loader import ROOT, init_series, list_templates, load_series
from core.brain import apply_character_lock, assemble_prompts
from core.text_utils import clean_for_tts, extract_sfx


class TextUtilsTests(unittest.TestCase):
    def test_extract_sfx_and_seed(self):
        vo, sfx = extract_sfx("Elias walks. [LOW HUM] (seed 123)")
        self.assertNotIn("seed", vo.lower())
        self.assertNotIn("[", vo)
        self.assertIn("LOW HUM", sfx)

    def test_clean_for_tts(self):
        text = clean_for_tts("Cold air. [STATIC] Elias (seed 9) waits.")
        self.assertNotIn("STATIC", text)
        self.assertNotIn("seed", text.lower())


class SchemaTests(unittest.TestCase):
    def test_episode_script_validation(self):
        data = {
            "episode_title": "Test",
            "hook": "Hook",
            "scenes": [
                {
                    "id": 1,
                    "voiceover": "Elias enters.",
                    "visual_prompt": "Radio station interior",
                    "duration": 5,
                    "sfx": "HUM",
                }
            ],
            "episode_summary": "He entered.",
            "next_status": "Deeper inside",
            "cliffhanger": "A light flickers",
        }
        script = EpisodeScript.model_validate(data)
        self.assertEqual(len(script.scenes), 1)

    def test_render_template(self):
        out = render_template("Hello {{name}}", {"name": "Elias"})
        self.assertEqual(out, "Hello Elias")


class PackTests(unittest.TestCase):
    def test_templates_exist(self):
        templates = list_templates()
        self.assertIn("analog_horror", templates)
        self.assertIn("generic_drama", templates)

    def test_load_void_signal(self):
        pack = load_series("void_signal")
        self.assertEqual(pack.config.slug, "void_signal")
        self.assertTrue(pack.world_bible)
        self.assertEqual(pack.protagonist().name, "Elias")
        self.assertEqual(pack.protagonist().visual_seed, 6661013)
        self.assertIn("narration_system", pack.prompts)

    def test_assemble_prompts_includes_bible_and_appearance(self):
        pack = load_series("void_signal")
        system, user = assemble_prompts(pack)
        self.assertIn("JSON", system)
        self.assertIn("Signals", user)
        self.assertIn("Elias", user)
        self.assertIn("grey parka", user.lower().replace("gray", "grey"))

    def test_character_lock_appended(self):
        pack = load_series("void_signal")
        script = EpisodeScript.model_validate(
            {
                "episode_title": "T",
                "hook": "h",
                "scenes": [
                    {
                        "id": 1,
                        "voiceover": "Elias (seed 6661013) waits. [HUM]",
                        "visual_prompt": "Dark hall",
                        "duration": 5,
                        "sfx": "",
                    }
                ],
                "episode_summary": "waited",
                "next_status": "next",
                "cliffhanger": "noise",
            }
        )
        locked = apply_character_lock(pack, script)
        self.assertNotIn("seed", locked.scenes[0].voiceover.lower())
        self.assertIn("HUM", locked.scenes[0].sfx)
        self.assertIn("CHARACTER LOCK", locked.scenes[0].visual_prompt)
        self.assertIn("Style:", locked.scenes[0].visual_prompt)
        self.assertIn("grey parka", locked.scenes[0].visual_prompt.lower())

    def test_init_series_from_template(self):
        slug = "_test_tmp_show"
        dest = ROOT / "series" / slug
        if dest.exists():
            import shutil

            shutil.rmtree(dest)
        init_series(slug, "generic_drama", name="Tmp Show")
        pack = load_series(slug)
        self.assertEqual(pack.config.name, "Tmp Show")
        self.assertNotEqual(pack.protagonist().visual_seed, 0)
        import shutil

        shutil.rmtree(dest)


class HardcodeGuardTests(unittest.TestCase):
    """Ensure core/ does not bake in VOID_SIGNAL identity."""

    FORBIDDEN = ["Elias", "DC Comics", "6661013", "VOID_SIGNAL", "void_signal"]

    def test_core_has_no_series_hardcodes(self):
        core = ROOT / "core"
        offenders = []
        for path in core.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in self.FORBIDDEN:
                if token in text:
                    offenders.append(f"{path.name}: {token}")
        self.assertEqual(offenders, [], msg=f"Hardcodes found: {offenders}")


class ProgressTests(unittest.TestCase):
    def test_history_for_prompt_empty(self):
        p = Progress()
        self.assertIn("No previous", p.history_for_prompt(5))


if __name__ == "__main__":
    unittest.main()
