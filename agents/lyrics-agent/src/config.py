import os
import platform
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Validate that the SDK will find credentials (HF_KEY OR both HF_API_KEY + HF_API_SECRET)
_hf_key = os.environ.get("HF_KEY")
_hf_api_key = os.environ.get("HF_API_KEY")
_hf_api_secret = os.environ.get("HF_API_SECRET")

if not _hf_key and not (_hf_api_key and _hf_api_secret):
    raise EnvironmentError(
        "Higgsfield credentials not set. In your .env file, set either:\n"
        "  HF_KEY=apikey:apisecret\n"
        "or both:\n"
        "  HF_API_KEY=...\n"
        "  HF_API_SECRET=..."
    )

# LRCLib
LRCLIB_BASE = "https://lrclib.net/api"

# Video dimensions (TikTok 9:16)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920

# Higgsfield model — verify with `higgsfield --help` or cloud.higgsfield.ai
HIGGSFIELD_MODEL = "bytedance/seedance-2.0/text-to-video"

# Polling
POLL_INTERVAL_SECONDS = 3
MAX_POLL_SECONDS = 300

# Output directory
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Font — Futura Bold on macOS, fallback on Linux
if platform.system() == "Darwin":
    FONT_PATH = "/System/Library/Fonts/Supplemental/Futura.ttc"
    FONT_INDEX = 2  # Bold weight
else:
    FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    FONT_INDEX = 0
