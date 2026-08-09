Write episode {{episode}} of "{{series_name}}" (genre: {{genre}}).

WORLD BIBLE:
{{world_bible}}

CHARACTERS:
{{characters}}

CURRENT STATUS:
{{current_status}}

PRIOR EPISODES:
{{plot_history}}

Produce exactly {{scene_count}} scenes.

Return ONLY this JSON shape:
{
  "episode_title": "string",
  "hook": "one-line viewer hook",
  "scenes": [
    {
      "id": 1,
      "voiceover": "Narration without seed numbers or SFX brackets.",
      "visual_prompt": "Scene-only action/location/camera. Character by name.",
      "duration": 5,
      "sfx": "OPTIONAL SFX LABEL"
    }
  ],
  "episode_summary": "2-3 sentences for series memory",
  "next_status": "Where the next episode should pick up",
  "cliffhanger": "Final unresolved beat"
}
