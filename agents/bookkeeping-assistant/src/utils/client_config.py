import json
import re
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(__file__).parent.parent / "config"
CLIENTS_DIR = CONFIG_DIR / "clients"
ACTIVE_CLIENT_FILE = CONFIG_DIR / "active_client.json"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def get_active_client() -> dict:
    data = json.loads(ACTIVE_CLIENT_FILE.read_text())
    if not data.get("slug"):
        raise RuntimeError(
            "No active client set. Run: python run.py --set-client <slug>"
        )
    return data


def set_active_client(slug: str) -> None:
    config_path = CLIENTS_DIR / f"{slug}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"No client config found at {config_path}")
    ACTIVE_CLIENT_FILE.write_text(json.dumps({"slug": slug}, indent=2))
    print(f"Active client set to: {slug}")


def load_client(slug: Optional[str] = None) -> dict:
    if slug is None:
        slug = get_active_client()["slug"]
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Client config not found: {path}")
    return json.loads(path.read_text())


def save_client(config: dict) -> None:
    slug = slugify(config["client_name"])
    path = CLIENTS_DIR / f"{slug}.json"
    path.write_text(json.dumps(config, indent=2))
    print(f"Client config saved: {path}")


def get_folder_id(client: dict, key: str) -> str:
    folder_id = client.get("folders", {}).get(key, "")
    if not folder_id:
        raise KeyError(f"Folder ID not set for key '{key}' in client '{client['client_name']}'")
    return folder_id
