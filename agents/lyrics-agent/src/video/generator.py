import time
from datetime import datetime
from pathlib import Path

import requests

from config import HIGGSFIELD_MODEL, OUTPUT_DIR


class VideoGenerationError(Exception):
    pass


def generate_video(prompt: str, clip_duration: int = 5) -> Path:
    """Submit a text-to-video job to Higgsfield, poll until done, download the MP4."""
    import higgsfield_client

    arguments = {
        "prompt": prompt,
        "aspect_ratio": "9:16",
        "duration": clip_duration,
        "resolution": "1080p",
        "mode": "std",
    }

    request_controller = _submit_with_retry(higgsfield_client, arguments)

    print("      Waiting for Higgsfield to generate your clip...")
    for status in request_controller.poll_request_status():
        cls = type(status).__name__
        if cls == "Queued":
            print("      Queued...")
        elif cls == "InProgress":
            print("      Generating...")
        elif cls == "Completed":
            video_url = status.result["video"]["url"]
            return _download(video_url)
        elif cls == "Failed":
            raise VideoGenerationError(f"Higgsfield generation failed: {status}")

    raise VideoGenerationError("Higgsfield returned no final status")


def _submit_with_retry(higgsfield_client, arguments: dict, retries: int = 1):
    for attempt in range(retries + 1):
        try:
            return higgsfield_client.submit(HIGGSFIELD_MODEL, arguments=arguments)
        except Exception as exc:
            if attempt == retries:
                raise VideoGenerationError(f"Failed to submit to Higgsfield: {exc}") from exc
            print(f"      Submit failed ({exc}), retrying in 5s...")
            time.sleep(5)


def _download(url: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = OUTPUT_DIR / f"raw_clip_{timestamp}.mp4"
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"      Raw clip saved to: {dest}")
    return dest
