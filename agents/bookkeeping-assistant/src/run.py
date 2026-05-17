#!/usr/bin/env python3
"""
Bookkeeping automation pipeline — CLI entry point.

Commands:
    # Set up a new client's Drive folder structure
    python run.py --new-client "Akuffo_2026"

    # Save the config after Claude Code creates the Drive folders
    python run.py --new-client "Akuffo_2026" --save-config '{"root_folder_id": "...", "folders": {...}}'

    # Switch active client
    python run.py --set-client akuffo_2026

    # Run an agent (Claude Code reads the plan and executes Drive I/O + API calls)
    python run.py --agent intake
    python run.py --agent coa
    python run.py --agent bank-feed
    python run.py --agent categorize
    python run.py --agent reconcile
    python run.py --agent review
    python run.py --agent journal
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _load(rel_path: str):
    """Load a Python module from a path relative to the project root."""
    full = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(full.stem, full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AGENT_FILES = {
    "intake":     "agents/01_intake/processor.py",
    "coa":        "agents/02_coa_builder/processor.py",
    "bank-feed":  "agents/03_bank_feed/processor.py",
    "categorize": "agents/04_categorization/processor.py",
    "reconcile":  "agents/05_reconciliation/processor.py",
    "review":     "agents/06_review/processor.py",
    "journal":    "agents/07_journal_entries/processor.py",
}


def cmd_new_client(client_name: str, save_config_json: Optional[str]) -> None:
    fb = _load("agents/00_onboarding/folder_builder.py")

    if save_config_json:
        data = json.loads(save_config_json)
        fb.save_config(client_name, data["root_folder_id"], data["folders"])
    else:
        plan = fb.creation_plan(client_name)
        print(json.dumps(plan, indent=2))


def cmd_set_client(slug: str) -> None:
    from utils.client_config import set_active_client
    set_active_client(slug)


def cmd_agent(agent_name: str) -> None:
    from utils.client_config import load_client
    client = load_client()

    # Agents that have a processor.py ready
    built = {
        "intake": _run_intake,
    }

    if agent_name in built:
        built[agent_name](client)
    elif agent_name == "coa":
        _run_coa(client)
    elif agent_name == "bank-feed":
        _run_bank_feed(client)
    elif agent_name == "categorize":
        _run_categorize(client)
    else:
        print(json.dumps({
            "agent": agent_name,
            "client": client["client_name"],
            "status": "not_yet_built",
            "message": f"Agent '{agent_name}' is not yet implemented.",
        }, indent=2))


def _run_bank_feed(client: dict) -> None:
    """
    Bank Feed / Transaction Normalization Agent.

    Claude Code flow:
    1. Search `03_Raw_Documents/` subfolders for CSV files:
       - Bank_Statements/ → source_type=bank
       - Credit_Cards/    → source_type=credit_card
       - Stripe/          → source_type=stripe
       - PayPal/          → source_type=paypal
    2. Download each CSV to /tmp/raw/{filename}
    3. Run processor once with all files:
         python agents/03_bank_feed/processor.py
           --input-file /tmp/raw/bank.csv --account-name "Chase Checking"
           --input-file /tmp/raw/amex.csv --account-name "AMEX Card 1" --source-type credit_card
           --input-file /tmp/raw/stripe.csv --account-name "Stripe"
           --output-normalized /tmp/normalized_transactions.csv
           --output-qb /tmp/qb_bank_feed.csv
           [--enrich]   # add flag to clean descriptions via Claude
    4. Upload normalized_transactions.csv → transactions_normalized folder
    5. Upload qb_bank_feed.csv → transactions_qb_upload folder
    """
    from utils.client_config import get_folder_id
    print(json.dumps({
        "agent": "bank-feed",
        "client": client["client_name"],
        "status": "ready",
        "raw_documents_folder": get_folder_id(client, "raw_documents"),
        "transactions_normalized_folder": get_folder_id(client, "transactions_normalized"),
        "transactions_qb_upload_folder": get_folder_id(client, "transactions_qb_upload"),
        "processor": "agents/03_bank_feed/processor.py",
        "source_type_map": {
            "Bank_Statements": "bank",
            "Credit_Cards": "credit_card",
            "Stripe": "stripe",
            "PayPal": "paypal",
            "Shopify": "shopify",
        },
        "outputs": {
            "normalized_transactions.csv": "transactions_normalized_folder",
            "qb_bank_feed.csv": "transactions_qb_upload_folder",
        },
    }, indent=2))


def _run_coa(client: dict) -> None:
    """
    COA Builder Agent.

    Claude Code flow:
    1. Download intake_structured.json from Drive (intake_structured folder)
       and save to /tmp/intake_structured.json
    2. Run: python agents/02_coa_builder/processor.py
               --intake-file /tmp/intake_structured.json
               --template-file shared/coa_templates/General_Service_Business_COA.csv
               --output-file /tmp/Final_COA_Import.csv
    3. Upload /tmp/Final_COA_Import.csv to Drive → coa folder as Final_COA_Import.csv
    """
    from utils.client_config import get_folder_id
    print(json.dumps({
        "agent": "coa",
        "client": client["client_name"],
        "status": "ready",
        "intake_structured_folder": get_folder_id(client, "intake_structured"),
        "coa_folder": get_folder_id(client, "coa"),
        "processor": "agents/02_coa_builder/processor.py",
        "run": (
            "python agents/02_coa_builder/processor.py "
            "--intake-file /tmp/intake_structured.json "
            "--template-file shared/coa_templates/General_Service_Business_COA.csv "
            "--output-file /tmp/Final_COA_Import.csv"
        ),
        "outputs": {
            "Final_COA_Import.csv": "coa_folder",
        },
    }, indent=2))


def _run_categorize(client: dict) -> None:
    """
    Categorization Agent.

    Claude Code flow:
    1. Download normalized_transactions.csv from Drive (transactions_normalized folder)
       → save to /tmp/normalized_transactions.csv
    2. Download Final_COA_Import.csv from Drive (coa folder)
       → save to /tmp/Final_COA_Import.csv
    3. Optionally download intake_structured.json (intake_structured folder)
       → save to /tmp/intake_structured.json
    4. Run: python agents/04_categorization/processor.py
               --normalized-file /tmp/normalized_transactions.csv
               --coa-file /tmp/Final_COA_Import.csv
               --intake-file /tmp/intake_structured.json
               --output-categorized /tmp/categorized_transactions.csv
               --output-review /tmp/review_required.csv
               -v
    5. Upload categorized_transactions.csv → transactions_categorized folder
    6. Upload review_required.csv → transactions_review_required folder
    """
    from utils.client_config import get_folder_id
    print(json.dumps({
        "agent": "categorize",
        "client": client["client_name"],
        "status": "ready",
        "transactions_normalized_folder": get_folder_id(client, "transactions_normalized"),
        "coa_folder": get_folder_id(client, "coa"),
        "intake_structured_folder": get_folder_id(client, "intake_structured"),
        "transactions_categorized_folder": get_folder_id(client, "transactions_categorized"),
        "transactions_review_required_folder": get_folder_id(client, "transactions_review_required"),
        "processor": "agents/04_categorization/processor.py",
        "run": (
            "python agents/04_categorization/processor.py "
            "--normalized-file /tmp/normalized_transactions.csv "
            "--coa-file /tmp/Final_COA_Import.csv "
            "--intake-file /tmp/intake_structured.json "
            "--output-categorized /tmp/categorized_transactions.csv "
            "--output-review /tmp/review_required.csv "
            "-v"
        ),
        "outputs": {
            "categorized_transactions.csv": "transactions_categorized_folder",
            "review_required.csv": "transactions_review_required_folder",
        },
    }, indent=2))


def _run_intake(client: dict) -> None:
    """
    Intake Analysis Agent.

    Claude Code flow:
    1. Use MCP to list files in the intake_transcripts folder
    2. Read the most recent transcript Google Doc with read_file_content
    3. Save the content to a temp file (e.g., /tmp/transcript.txt)
    4. Run: python agents/01_intake/processor.py --transcript-file /tmp/transcript.txt
    5. Parse the JSON output
    6. Save output["structured_data"] as intake_structured.json → intake_structured folder
    7. Save output["summary_text"] as COA_Intake_Summary.txt → intake_summaries folder
    """
    from utils.client_config import get_folder_id
    print(json.dumps({
        "agent": "intake",
        "client": client["client_name"],
        "status": "ready",
        "intake_transcripts_folder": get_folder_id(client, "intake_transcripts"),
        "intake_summaries_folder": get_folder_id(client, "intake_summaries"),
        "intake_structured_folder": get_folder_id(client, "intake_structured"),
        "processor": "agents/01_intake/processor.py",
        "run": "python agents/01_intake/processor.py --transcript-file /tmp/transcript.txt",
        "outputs": {
            "intake_structured.json": "intake_structured_folder",
            "COA_Intake_Summary.txt": "intake_summaries_folder",
        },
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bookkeeping automation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--new-client", metavar="NAME",
                       help="Create Drive folders for a new client")
    group.add_argument("--set-client", metavar="SLUG",
                       help="Set the active client by slug")
    group.add_argument("--agent", metavar="NAME", choices=list(AGENT_FILES),
                       help="Run an agent against the active client")

    parser.add_argument("--save-config", metavar="JSON",
                        help="Used with --new-client: JSON payload of Drive folder IDs to save")

    args = parser.parse_args()

    if args.new_client:
        cmd_new_client(args.new_client, args.save_config)
    elif args.set_client:
        cmd_set_client(args.set_client)
    elif args.agent:
        cmd_agent(args.agent)


if __name__ == "__main__":
    main()
