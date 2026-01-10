**NOTE: WIP, Readme generated via AI**

# Episodic AI Content Factory

An automated, budget-friendly pipeline for generating high-retention, episodic AI video series. Built for creators aiming to hit social media monetization milestones via consistent, high-quality storytelling.

## Key Features

* **Consistency Engine:** Uses a "World Bible" and character seeding to ensure characters and environments look the same across all episodes—no AI slop.
* **Episodic Logic:** Remembers past events to build a continuous narrative arc rather than random clips.
* **One-Click Funnel:** Integrated with OpenRouter (Gemini 3 Flash / Nano Banana) for low-cost, high-fidelity generation.
* **Auto-Post & SEO:** Automatically generates viral-ready titles, descriptions, and tags, then posts to YouTube Shorts, TikTok, and Instagram Reels.
* **Budget First:** Orchestrated in Python and FFmpeg to avoid expensive SaaS subscriptions.

## Project Structure

```
/ai-video-funnel
├── main.py                 # The Daily Conductor (Runs the loop)
├── .env.example            # Template for API keys (OpenRouter, Google, TikTok)
├── requirements.txt        # python-dotenv, openai, google-api-python-client
│
├── /database               # Long-term Memory
│   ├── series_progress.json # Tracks current episode, character seeds, & plot points
│   └── world_bible.txt      # The "Truth" of your universe for the AI
│
├── /core                   # The Logic Modules
│   ├── brain.py            # OpenRouter orchestrator (Script & JSON Gen)
│   ├── assets.py           # Media handling (Video clips & TTS audio)
│   ├── compiler.py         # FFmpeg engine for stitching & subtitles
│   └── uploader.py         # Social media API integration
│
└── /output                 # Local storage for archives
    ├── /temp               # Ephemeral clips per run
    └── /final              # Final .mp4 exports organized by episode
```

### Quick Start
#### 1. Prerequisites
- Python 3.10+
- FFmpeg (installed on your system path)
- OpenRouter API Key

#### 2. Installation
```
git clone [https://github.com/yourusername/ai-video-funnel.git](https://github.com/yourusername/ai-video-funnel.git)
cd ai-video-funnel
pip install -r requirements.txt
```

#### 3. Configuration
Rename .env.example to .env and add your keys:
```
OPENROUTER_API_KEY=your_key_here
YOUTUBE_CLIENT_ID=your_id_here
SERIES_NAME="The Last Cyberpunk"
POSTING_FREQUENCY=2  # Number of videos per day
```

#### 4. Run the Factory
- Bash
- python main.py


### Monetization Strategy
This repo is designed to solve the "Retention Problem." By using episodic cliffhangers and visual consistency, the funnel targets the YouTube Shorts algorithm's "Viewed vs. Swiped Away" metric.
Part 1: The Hook (Pattern Interrupt)
Part 2: Story Development (Consistent Characters)
Part 3: The Bridge (Cliffhanger for Episode 2)

### Contributing
I am building this to reach monetization by the end of the month. If you want to contribute to the auto-subtitling engine or the Instagram API module, feel free to open a PR
