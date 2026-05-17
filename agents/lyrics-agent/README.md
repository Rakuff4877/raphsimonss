# TikTok Lyric Video Generator

**Paste an Apple Music link — get a cinematic AI lyric video ready to upload to TikTok**

## Problem

Creating lyric videos for TikTok is tedious: find the lyrics, time each line manually, source or generate a video background, composite the text, export in the right format. Doing this well takes video editing skills and 30–60 minutes per song.

## Solution

A Python agent that takes an Apple Music URL (or song + artist name) and produces a finished, upload-ready TikTok lyric video in under 2 minutes. It fetches timestamped lyrics automatically, generates a unique cinematic AI video background via Higgsfield, and burns the lyrics onto the video with precise karaoke-style timing.

The output is a silent 9:16 MP4 — drop it into TikTok's editor, add the song, post.

## How It Works

1. **Song resolution** — Apple Music URL or `--song` / `--artist` flags
2. **Lyrics fetch** — LRCLib API returns millisecond-accurate LRC timestamps
3. **AI video generation** — Higgsfield generates a 1080p 9:16 cinematic clip from a curated prompt library (12 prompts: coastal drives, landscapes, urban rooftops, intimate scenes)
4. **Compositing** — ffmpeg loops the clip to match lyric duration; Pillow renders each line as a transparent PNG; ffmpeg overlays them with frame-accurate timing

## Usage

```bash
pip install -r requirements.txt
brew install ffmpeg  # macOS

cp .env.example .env
# Add HIGGSFIELD_API_KEY to .env

# From an Apple Music URL
python main.py "https://music.apple.com/..."

# From song + artist
python main.py --song "Blinding Lights" --artist "The Weeknd"

# Custom duration and clip length
python main.py --song "Blinding Lights" --artist "The Weeknd" --duration 30 --clip-duration 10

# Reuse an existing raw clip (saves Higgsfield credits while iterating on styling)
python main.py --song "Blinding Lights" --artist "The Weeknd" --skip-generate --raw-clip output/raw_clip.mp4
```

Output is saved to `output/{song}_{artist}_{timestamp}.mp4`.

## Results

- Full lyric video in under 2 minutes end-to-end
- Zero manual timing — LRC timestamps drive every line automatically
- Tested across multiple genres (The Weeknd, Fred again.., Charlotte Day Wilson, Gotts Street Park)
- TikTok-native format (9:16, 1080p) — no post-processing needed before upload

> Add your `HIGGSFIELD_API_KEY` to `.env`. Never commit the `.env` file.
