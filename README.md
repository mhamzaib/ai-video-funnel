# Multi-Series AI Video Funnel

Automated vertical Shorts pipeline: **story → TTS + Flux stills → FFmpeg Ken Burns → YouTube metadata/upload**, driven by **series packs** so you can run any genre without editing Python.

## Key Features

* **Consistency Engine:** Uses a "World Bible" and character seeding to ensure characters and environments look the same across all episodes—no AI slop.
* **Episodic Logic:** Remembers past events to build a continuous narrative arc rather than random clips.
* **One-Click Funnel:** Integrated with model-driven generation and FFmpeg for low-cost, automated Shorts creation.
* **Auto-Post & SEO:** Automatically generates YouTube-ready titles, descriptions, and tags and handles upload dry-run safety.
* **Budget First:** Orchestrated in Python and FFmpeg to avoid expensive SaaS subscriptions.

## Quick start

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
# Install FFmpeg and put it on PATH
copy .env.example .env         # fill OPENAI_API_KEY, FAL_KEY
```

## Project Structure

```
/ai-video-funnel
├── main.py                 # The Daily Conductor (Runs the loop)
├── .env.example            # Template for API keys
├── requirements.txt        # python-dotenv, openai, google-api-python-client
│
├── /database               # Long-term Memory
│   ├── series_progress.json # Tracks current episode, character seeds, & plot points
│   └── world_bible.txt      # The "Truth" of your universe for the AI
│
├── /core                   # The Logic Modules
│   ├── brain.py            # LLM orchestrator and script generation
│   ├── assets.py           # Media handling (images + TTS audio)
│   ├── compiler.py         # FFmpeg engine for stitching & captions
│   └── uploader.py         # YouTube upload integration
│
└── /output                 # Local storage for exports
    ├── /temp               # Ephemeral clips per run
    └── /final              # Final .mp4 exports organized by episode
```

### Run VOID_SIGNAL (example pack)

```bash
# Full funnel (upload dry-run skips live YouTube)
python main.py run --series void_signal --dry-run

# Partial stages
python main.py run --series void_signal --stages brain,assets,compile
python main.py status --series void_signal
```

### Start a new series

```bash
python main.py templates
python main.py init --slug my_show --template analog_horror --name "My Show"
# Edit series/my_show/world_bible.md and characters.yaml appearance lock
python main.py run --series my_show --stages brain --review-script --dry-run
```

### Lifecycle

```bash
python main.py archive --series my_show
python main.py archive --series my_show --complete
python main.py activate --series my_show
```

### Run VOID_SIGNAL (example pack)

```bash
# Full funnel (upload dry-run skips live YouTube)
python main.py run --series void_signal --dry-run

# Partial stages
python main.py run --series void_signal --stages brain,assets,compile
python main.py status --series void_signal
```

### Start a new series

```bash
python main.py templates
python main.py init --slug my_show --template analog_horror --name "My Show"
# Edit series/my_show/world_bible.md and characters.yaml appearance lock
python main.py run --series my_show --stages brain --review-script --dry-run
```

### Lifecycle

```bash
python main.py archive --series my_show
python main.py archive --series my_show --complete
python main.py activate --series my_show
```

## Series pack layout

```
series/<slug>/
  series.yaml          # genre, style_prompt, models, caption, privacy
  characters.yaml      # appearance lock + visual_seed + TTS voice
  world_bible.md
  progress.json        # episode counter + plot_history
  prompts/             # narration + metadata templates
  output/episodes/NNN/ # script, assets, final.mp4, metadata
```

Character consistency = **locked appearance string** + **Flux seed from pack** + style from `series.yaml`. Seed numbers are never spoken in VO.

## YouTube setup

1. Create a Google Cloud OAuth client (Desktop app).
2. Save JSON to `secrets/youtube_client_secrets.json`.
3. First upload opens a browser for consent; token cached at `secrets/youtube_token.json`.
4. Use `--dry-run` until you are ready; default privacy is `unlisted` in packs.

## Tests

```bash
python -m unittest tests.test_pipeline -v
```

## New series checklist

1. `python main.py init --slug … --template analog_horror|generic_drama`
2. Fill `world_bible.md` and tighten `characters.yaml` appearance
3. Set `seo_keywords` / `style_prompt` in `series.yaml`
4. `run --stages brain --review-script`
5. `run --stages assets,compile,seo --episode N --dry-run`
6. Upload when ready (remove `--dry-run`)
