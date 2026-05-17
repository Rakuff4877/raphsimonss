import argparse
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a TikTok lyric video using Higgsfield AI and LRCLib"
    )
    parser.add_argument(
        "url", nargs="?", default=None,
        help="Apple Music link (alternative to --song / --artist)",
    )
    parser.add_argument("--song", default=None, help="Song title")
    parser.add_argument("--artist", default=None, help="Artist name")
    parser.add_argument(
        "--duration", type=float, default=45,
        help="Cap lyrics at N seconds (default: 45)",
    )
    parser.add_argument(
        "--clip-duration", type=int, default=5, choices=[5, 10],
        dest="clip_duration",
        help="Higgsfield clip length in seconds (default: 5)",
    )
    parser.add_argument(
        "--prompt-index", type=int, default=None, dest="prompt_index",
        help="Force a specific aesthetic prompt template 0-9",
    )
    parser.add_argument(
        "--skip-generate", action="store_true", dest="skip_generate",
        help="Skip Higgsfield generation and reuse an existing raw clip",
    )
    parser.add_argument(
        "--raw-clip", type=str, default=None, dest="raw_clip",
        help="Path to existing raw clip (required with --skip-generate)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Config import validates env vars and creates output/
    try:
        import config
    except EnvironmentError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    from lyrics.fetcher import LyricsNotFoundError, fetch_synced_lyrics
    from lyrics.parser import parse_lrc
    from video.editor import FFmpegError, check_ffmpeg, loop_video, overlay_lyrics
    from video.generator import VideoGenerationError, generate_video
    from video.prompts import select_prompt

    # Resolve song + artist from URL or flags
    if args.url:
        from lyrics.apple_music import resolve_apple_music_url
        try:
            song, artist = resolve_apple_music_url(args.url)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Identified: '{song}' by {artist}")
    elif args.song and args.artist:
        song, artist = args.song, args.artist
    else:
        print(
            "Error: provide either an Apple Music URL or both --song and --artist",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate ffmpeg early
    try:
        check_ffmpeg()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 1. Fetch lyrics
    print(f"[1/4] Fetching synced lyrics for '{song}' by {artist}...")
    try:
        raw_lrc = fetch_synced_lyrics(song, artist)
    except LyricsNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Parse LRC
    print("[2/4] Parsing LRC timestamps...")
    lyrics = parse_lrc(raw_lrc, max_duration=args.duration)
    if not lyrics:
        print("Error: no lyric lines found after parsing.", file=sys.stderr)
        sys.exit(1)
    total_duration = lyrics[-1].end
    print(f"      {len(lyrics)} lines, {total_duration:.1f}s total")

    # 3. Generate or reuse raw clip
    if args.skip_generate:
        if not args.raw_clip:
            print("Error: --raw-clip PATH is required with --skip-generate", file=sys.stderr)
            sys.exit(1)
        raw_clip_path = Path(args.raw_clip)
        if not raw_clip_path.exists():
            print(f"Error: raw clip not found: {raw_clip_path}", file=sys.stderr)
            sys.exit(1)
        print(f"[3/4] Reusing existing clip: {raw_clip_path}")
    else:
        print("[3/4] Generating AI video clip via Higgsfield...")
        prompt_idx, prompt = select_prompt(seed=args.prompt_index)
        print(f"      Prompt #{prompt_idx + 1}: {prompt[:80]}...")
        try:
            raw_clip_path = generate_video(prompt, clip_duration=args.clip_duration)
        except VideoGenerationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    # 4. Loop + overlay lyrics
    print("[4/4] Compositing lyrics onto video...")
    looped_path = config.OUTPUT_DIR / "looped_temp.mp4"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = f"{song}_{artist}".replace(" ", "_").lower()
    final_path = config.OUTPUT_DIR / f"{slug}_{timestamp}.mp4"

    try:
        loop_video(raw_clip_path, total_duration, looped_path)
        overlay_lyrics(looped_path, lyrics, final_path, font_size=80)
    except FFmpegError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if looped_path.exists():
            looped_path.unlink()

    print(f"\nDone! Video saved to: {final_path}")
    print("Note: Video is silent — add music in TikTok's editor after uploading.")


if __name__ == "__main__":
    main()
