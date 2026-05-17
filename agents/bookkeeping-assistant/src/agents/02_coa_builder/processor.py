#!/usr/bin/env python3
"""
COA Builder Agent — processor.

Reads intake_structured.json and a base COA template CSV, calls Claude to
build a customized Chart of Accounts, and outputs a QuickBooks-ready CSV.

Usage:
    python processor.py \\
        --intake-file /tmp/intake_structured.json \\
        --template-file shared/coa_templates/General_Service_Business_COA.csv

    python processor.py \\
        --intake-file /tmp/intake_structured.json \\
        --template-file shared/coa_templates/General_Service_Business_COA.csv \\
        --output-file /tmp/Final_COA_Import.csv

Output (stdout or --output-file):
    QuickBooks-ready CSV with columns:
    Account Number, Account Name, Account Type, Detail Type, Description
"""

import anthropic
import argparse
import csv
import json
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT = (AGENT_DIR / "agent.md").read_text()
DEFAULT_MODEL = "claude-opus-4-7"

QB_COLUMNS = ["Account Number", "Account Name", "Account Type", "Detail Type", "Description"]


def make_output_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "accounts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "account_number": {"type": "string"},
                        "account_name": {"type": "string"},
                        "account_type": {"type": "string"},
                        "detail_type": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": [
                        "account_number", "account_name",
                        "account_type", "detail_type", "description",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["accounts"],
        "additionalProperties": False,
    }


def build_coa(intake: dict, template_csv: str, model: str = DEFAULT_MODEL) -> list[dict]:
    client = anthropic.Anthropic()
    schema = make_output_schema()

    user_message = (
        "Build a customized Chart of Accounts for this client.\n\n"
        "BASE COA TEMPLATE (CSV):\n"
        f"{template_csv}\n\n"
        "CLIENT INTAKE DATA (JSON):\n"
        f"{json.dumps(intake, indent=2)}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user_message}],
    )

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["accounts"]


def accounts_to_csv(accounts: list[dict]) -> str:
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=QB_COLUMNS)
    writer.writeheader()
    for acct in accounts:
        writer.writerow({
            "Account Number": acct["account_number"],
            "Account Name": acct["account_name"],
            "Account Type": acct["account_type"],
            "Detail Type": acct["detail_type"],
            "Description": acct.get("description", ""),
        })
    return buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="COA Builder Agent")
    parser.add_argument("--intake-file", required=True,
                        help="Path to intake_structured.json")
    parser.add_argument("--template-file", required=True,
                        help="Path to base COA template CSV")
    parser.add_argument("--output-file", default=None,
                        help="Output CSV path (default: stdout)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    intake = json.loads(Path(args.intake_file).read_text(encoding="utf-8"))
    template_csv = Path(args.template_file).read_text(encoding="utf-8")

    print(f"Building COA for {intake.get('client_name', 'unknown client')}...", file=sys.stderr)
    accounts = build_coa(intake, template_csv, model=args.model)
    print(f"Generated {len(accounts)} accounts.", file=sys.stderr)

    csv_output = accounts_to_csv(accounts)

    if args.output_file:
        Path(args.output_file).write_text(csv_output, encoding="utf-8")
        print(f"Saved to {args.output_file}", file=sys.stderr)
    else:
        print(csv_output, end="")


if __name__ == "__main__":
    main()
