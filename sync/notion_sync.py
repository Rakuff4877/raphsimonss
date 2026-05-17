"""
Syncs agent case studies from local YAML files to a Notion database.

Usage:
    pip install -r requirements.txt
    cp ../.env.example ../.env && fill in values
    python notion_sync.py

Required env vars (set in ../.env):
    NOTION_TOKEN        - Notion integration token
    NOTION_DATABASE_ID  - Agents database ID
"""

import os
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client

load_dotenv(Path(__file__).parent.parent / ".env")

TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")


def validate_env():
    missing = [k for k in ("NOTION_TOKEN", "NOTION_DATABASE_ID") if not os.environ.get(k)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)


def load_case_studies():
    root = Path(__file__).parent.parent / "agents"
    studies = []
    for path in sorted(root.glob("*/case_study.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
            data["_path"] = str(path)
            studies.append(data)
    return studies


def find_existing_page(client, title):
    results = client.databases.query(
        database_id=DATABASE_ID,
        filter={"property": "Name", "title": {"equals": title}},
    )
    pages = results.get("results", [])
    return pages[0]["id"] if pages else None


def build_properties(study):
    props = {
        "Name": {"title": [{"text": {"content": study.get("title", "")}}]},
        "Tagline": {"rich_text": [{"text": {"content": study.get("tagline", "")}}]},
        "Status": {"select": {"name": study.get("status", "Concept")}},
        "Complexity": {"select": {"name": study.get("complexity", "Medium")}},
        "Category": {"select": {"name": study.get("category", "")}},
        "Tech Stack": {"multi_select": [{"name": t} for t in study.get("tech_stack", [])]},
    }
    if study.get("demo_url"):
        props["Demo"] = {"url": study["demo_url"]}
    if study.get("github_url"):
        props["GitHub"] = {"url": study["github_url"]}
    return props


def build_content_blocks(study):
    sections = [
        ("Problem", study.get("problem", "")),
        ("Solution", study.get("solution", "")),
        ("Architecture", study.get("architecture", "")),
        ("Results", study.get("results", "")),
    ]
    blocks = []
    for heading, body in sections:
        if not body:
            continue
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": heading}}]},
        })
        for paragraph in body.strip().split("\n\n"):
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": paragraph.strip()}}]},
            })
    return blocks


def sync_study(client, study):
    title = study.get("title", "")
    if not title:
        print(f"  Skipping {study['_path']} — no title")
        return

    properties = build_properties(study)
    existing_id = find_existing_page(client, title)

    if existing_id:
        client.pages.update(page_id=existing_id, properties=properties)
        print(f"  Updated: {title}")
    else:
        page = client.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties,
            children=build_content_blocks(study),
        )
        print(f"  Created: {title} ({page['id']})")


def main():
    validate_env()
    client = Client(auth=TOKEN)
    studies = load_case_studies()

    if not studies:
        print("No case studies found under agents/*/case_study.yaml")
        sys.exit(0)

    print(f"Syncing {len(studies)} case study/studies to Notion...")
    for study in studies:
        sync_study(client, study)
    print("Done.")


if __name__ == "__main__":
    main()
