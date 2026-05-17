"""
Client onboarding: canonical Drive folder structure and config generation.

This module defines the folder tree that every client gets. Claude Code reads
this plan and creates the folders via MCP, then passes the resulting folder IDs
back to generate_client_config() to write the local config file.

Usage (via run.py):
    python run.py --new-client "Akuffo_2026"
        → Prints JSON plan describing which folders to create and in what order.
          Claude Code executes the MCP calls, collects folder IDs, then calls:

    python run.py --new-client "Akuffo_2026" --save-config '{"root_folder_id": "...", "folders": {...}}'
        → Writes config/clients/akuffo_2026.json and sets it as active client.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.client_config import slugify, save_client, set_active_client

# Canonical folder tree. Every client gets this exact structure.
# Keys are folder names; values are dicts of subfolders (empty dict = leaf).
FOLDER_STRUCTURE: dict = {
    "00_Admin": {
        "Engagement_Letter": {},
        "Contracts_Pricing": {},
        "ID_Verification": {},
    },
    "01_Intake": {
        "Transcripts": {},
        "Intake_Notes": {},
        "Intake_Summaries": {},
        "Structured_Data": {},
    },
    "02_Accounting_System": {
        "Chart_of_Accounts": {},
        "Client_Rules": {},
        "Drafts": {},
    },
    "03_Raw_Documents": {
        "Bank_Statements": {},
        "Credit_Cards": {},
        "Stripe": {},
        "PayPal": {},
        "Shopify": {},
        "Receipts": {},
        "Invoices": {},
        "Other": {},
    },
    "04_Transactions": {
        "Normalized": {},
        "Categorized": {},
        "Review_Required": {},
        "QB_Upload": {},
        "Reports": {},
    },
    "05_Reconciliations": {
        "Inputs": {},
        "Outputs": {},
        "Issues_Flagged": {},
    },
    "06_Journal_Entries": {
        "Proposed": {},
        "Approved": {},
        "Posted": {},
    },
    "07_QuickBooks": {
        "Exports": {},
        "Uploads": {},
        "Backups": {},
        "Reconciliation_Screenshots": {},
    },
    "08_Reports": {
        "Profit_and_Loss": {},
        "Balance_Sheet": {},
        "Cash_Flow": {},
        "Monthly_Summaries": {},
    },
    "09_Tax": {
        "Prior_Tax_Returns": {},
        "1099s": {},
        "Year_End_Prep": {},
    },
    "10_Communication": {
        "Client_Emails": {},
        "Follow_Ups": {},
        "Meeting_Notes": {},
    },
}

# Maps Drive folder paths to client config keys.
# Only the folders that agents actually read from or write to are mapped.
FOLDER_CONFIG_KEYS: dict[str, str] = {
    "00_Admin": "admin",
    "01_Intake/Transcripts": "intake_transcripts",
    "01_Intake/Intake_Summaries": "intake_summaries",
    "01_Intake/Structured_Data": "intake_structured",
    "02_Accounting_System/Chart_of_Accounts": "coa",
    "02_Accounting_System/Client_Rules": "client_rules",
    "03_Raw_Documents": "raw_documents",
    "04_Transactions/Normalized": "transactions_normalized",
    "04_Transactions/Categorized": "transactions_categorized",
    "04_Transactions/Review_Required": "transactions_review_required",
    "04_Transactions/QB_Upload": "transactions_qb_upload",
    "05_Reconciliations/Outputs": "reconciliation_outputs",
    "05_Reconciliations/Issues_Flagged": "reconciliation_issues",
    "06_Journal_Entries/Proposed": "journal_proposed",
    "06_Journal_Entries/Approved": "journal_approved",
    "06_Journal_Entries/Posted": "journal_posted",
    "07_QuickBooks/Uploads": "qb_uploads",
    "10_Communication/Meeting_Notes": "meeting_notes",
}


def _flatten(structure: dict, parent_path: str = "") -> list[dict]:
    """Flattens the nested FOLDER_STRUCTURE into an ordered list for sequential creation."""
    items = []
    for name, children in structure.items():
        path = f"{parent_path}/{name}" if parent_path else name
        items.append({
            "name": name,
            "path": path,
            "parent_path": parent_path or None,
            "config_key": FOLDER_CONFIG_KEYS.get(path),
        })
        if children:
            items.extend(_flatten(children, path))
    return items


def creation_plan(client_name: str) -> dict:
    """Returns the JSON plan Claude Code uses to create Drive folders."""
    slug = slugify(client_name)
    folders = _flatten(FOLDER_STRUCTURE)
    return {
        "action": "create_client_folders",
        "client_name": client_name,
        "client_slug": slug,
        "root_folder_name": client_name,
        "parent_folder_name": "01_Clients",
        "folders": folders,
        "config_output_path": f"config/clients/{slug}.json",
        "instructions": (
            "1. Search Drive for a folder named '01_Clients' to get its ID.\n"
            "2. Create a folder named '{client_name}' inside 01_Clients. Record its ID as root_folder_id.\n"
            "3. Create each folder in 'folders' in order. Each folder's parent is identified by its "
            "parent_path (None = root client folder). Record each folder's Drive ID.\n"
            "4. If a folder already exists (search by name + parent), reuse its ID — don't create a duplicate.\n"
            "5. Call: python run.py --new-client '{client_name}' --save-config '<json>' "
            "where <json> = {{\"root_folder_id\": \"...\", \"folders\": {{\"<config_key>\": \"<id>\", ...}}}}"
        ).format(client_name=client_name),
    }


def generate_client_config(client_name: str, root_folder_id: str, folder_ids: dict) -> dict:
    """Builds the client config dict from folder IDs collected after Drive creation."""
    template_keys = [
        "admin", "intake_transcripts", "intake_summaries", "intake_structured",
        "coa", "client_rules", "raw_documents",
        "transactions_normalized", "transactions_categorized",
        "transactions_review_required", "transactions_qb_upload",
        "reconciliation_outputs", "reconciliation_issues",
        "journal_proposed", "journal_approved", "journal_posted",
        "qb_uploads", "meeting_notes",
    ]
    folders = {key: folder_ids.get(key, "") for key in template_keys}
    return {
        "client_name": client_name,
        "drive_root_folder_id": root_folder_id,
        "folders": folders,
        "model": "claude-sonnet-4-6",
        "industry": "",
        "coa_template": "",
    }


def save_config(client_name: str, root_folder_id: str, folder_ids: dict) -> None:
    """Generates, saves, and activates a new client config."""
    config = generate_client_config(client_name, root_folder_id, folder_ids)
    save_client(config)
    set_active_client(slugify(client_name))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("client_name")
    parser.add_argument("--save-config", help="JSON with root_folder_id and folders dict")
    args = parser.parse_args()

    if args.save_config:
        data = json.loads(args.save_config)
        save_config(args.client_name, data["root_folder_id"], data["folders"])
    else:
        plan = creation_plan(args.client_name)
        print(json.dumps(plan, indent=2))
