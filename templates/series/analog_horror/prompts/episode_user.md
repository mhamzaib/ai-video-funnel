Write episode {{episode}} of "{{series_name}}" (genre: {{genre}}).

EPISODE MODE: {{episode_mode}}
{{pilot_brief}}

Pronouns for the lead: {{pronouns}}. After first mention of their name, use pronouns.

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
  "hook": "one concrete hook, not a vague question",
  "scenes": [
    {
      "id": 1,
      "voiceover": "Spoken narration. Name once total across episode, then pronouns.",
      "delivery": "Pace/volume/pause directions for the performer.",
      "visual_prompt": "Scene-only action/location/camera.",
      "duration": 5,
      "sfx": "OPTIONAL SFX LABEL"
    }
  ],
  "episode_summary": "2-3 sentences for series memory",
  "next_status": "Where the next episode should pick up",
  "cliffhanger": "Final unresolved beat"
}
