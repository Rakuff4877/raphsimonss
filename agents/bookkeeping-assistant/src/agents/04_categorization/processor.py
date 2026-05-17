#!/usr/bin/env python3
"""
Categorization Agent — processor.

Reads normalized_transactions.csv + Final_COA_Import.csv,
applies optional vendor rules, then categorizes each transaction
against the Chart of Accounts using Claude.

Usage:
    python agents/04_categorization/processor.py \\
        --normalized-file /tmp/normalized_transactions.csv \\
        --coa-file /tmp/Final_COA_Import.csv \\
        --output-categorized /tmp/categorized_transactions.csv \\
        --output-review /tmp/review_required.csv

    python agents/04_categorization/processor.py \\
        --normalized-file /tmp/normalized_transactions.csv \\
        --coa-file /tmp/Final_COA_Import.csv \\
        --client-rules /tmp/client_rules.json \\
        --intake-file /tmp/intake_structured.json \\
        --output-categorized /tmp/categorized_transactions.csv \\
        --output-review /tmp/review_required.csv \\
        -v

Columns added to each row:
    coa_account_number, coa_account_name, confidence,
    needs_review, categorization_notes
"""

import anthropic
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT_BASE = (AGENT_DIR / "agent.md").read_text()
DEFAULT_MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 20


def load_coa(coa_file: str) -> list:
    with open(coa_file, newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


def load_vendor_rules(rules_file: str) -> list:
    data = json.loads(Path(rules_file).read_text(encoding="utf-8"))
    return data.get("vendor_rules", [])


def load_shared_rules() -> list:
    shared = Path(__file__).parent.parent.parent / "shared" / "vendor_rules.json"
    if shared.exists():
        data = json.loads(shared.read_text(encoding="utf-8"))
        return data.get("vendor_rules", [])
    return []


def build_system_prompt(accounts: list, intake: Optional[dict]) -> str:
    coa_lines = "\n".join(
        f"  {a['Account Number']} | {a['Account Name']} | {a['Account Type']}"
        + (f" | {a['Description']}" if a.get("Description") else "")
        for a in accounts
    )

    context = ""
    if intake:
        revenue = ", ".join(intake.get("revenue_streams", []))
        processors = ", ".join(intake.get("payment_processors", []))
        context = (
            f"\n\n## Client Business Context\n"
            f"- Business: {intake.get('client_name', 'Unknown')}\n"
            f"- Industry: {intake.get('industry', 'Unknown')}\n"
            f"- Revenue streams: {revenue}\n"
            f"- Payment processors: {processors}\n"
        )

    return SYSTEM_PROMPT_BASE + context + f"\n\n## Chart of Accounts\n\n{coa_lines}"


def make_schema(account_numbers: list) -> dict:
    all_codes = account_numbers + ["UNKNOWN"]
    return {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "account_number": {"type": "string", "enum": all_codes},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "notes": {"type": "string"},
                    },
                    "required": ["index", "account_number", "confidence", "notes"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }


def apply_vendor_rules(row: dict, rules: list) -> Optional[dict]:
    text = " ".join(filter(None, [
        row.get("description", ""),
        row.get("description_clean", ""),
        row.get("vendor", ""),
    ])).upper()

    for rule in rules:
        pattern = rule.get("vendor_pattern", "").upper()
        if pattern and re.search(re.escape(pattern), text):
            return {
                "account_number": rule["account_number"],
                "account_name": rule.get("account_name", ""),
                "confidence": rule.get("confidence", "high"),
                "notes": rule.get("notes", f"Vendor rule: {pattern}"),
            }
    return None


def categorize_batch(
    client: anthropic.Anthropic,
    batch: list,
    system_prompt: str,
    schema: dict,
    model: str,
) -> list:
    items = [
        {
            "index": orig_idx,
            "date": row.get("date", ""),
            "description": row.get("description", ""),
            "description_clean": row.get("description_clean", ""),
            "vendor": row.get("vendor", ""),
            "amount": row.get("amount", ""),
            "source_type": row.get("source_type", ""),
            "account_name": row.get("account_name", ""),
        }
        for orig_idx, row in batch
    ]

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{
            "role": "user",
            "content": (
                "Assign a COA account to each transaction. "
                "Return exactly one result per item, preserving the index.\n\n"
                + json.dumps(items, indent=2)
            ),
        }],
    )

    text = next(b.text for b in response.content if b.type == "text")
    return sorted(json.loads(text)["results"], key=lambda r: r["index"])


def process(
    normalized_file: str,
    coa_file: str,
    output_categorized: str,
    output_review: str,
    client_rules_file: Optional[str],
    intake_file: Optional[str],
    review_threshold: str,
    model: str,
    verbose: bool,
) -> None:
    accounts = load_coa(coa_file)
    coa_lookup = {a["Account Number"]: a for a in accounts}
    account_numbers = list(coa_lookup.keys())

    intake = None
    if intake_file:
        intake = json.loads(Path(intake_file).read_text(encoding="utf-8"))

    vendor_rules = load_shared_rules()
    if client_rules_file:
        vendor_rules = load_vendor_rules(client_rules_file) + vendor_rules

    with open(normalized_file, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if verbose:
        print(
            f"Loaded {len(rows)} transactions, {len(accounts)} COA accounts, "
            f"{len(vendor_rules)} vendor rules.",
            file=sys.stderr,
        )

    system_prompt = build_system_prompt(accounts, intake)
    schema = make_schema(account_numbers)
    client = anthropic.Anthropic()

    # Phase 1: pre-categorize without Claude API calls
    cat_results: dict = {}  # idx → categorization dict
    needs_claude: list = []

    for idx, row in enumerate(rows):
        if row.get("is_transfer", "N") == "Y":
            cat_results[idx] = {
                "account_number": "TRANSFER",
                "account_name": "Internal Transfer",
                "confidence": "high",
                "needs_review": "N",
                "categorization_notes": "Internal transfer — excluded from QB upload",
            }
            continue

        if row.get("is_duplicate", "N") == "Y":
            cat_results[idx] = {
                "account_number": "DUPLICATE",
                "account_name": "Duplicate — Excluded",
                "confidence": "high",
                "needs_review": "Y",
                "categorization_notes": "Flagged as duplicate — confirm and remove if correct",
            }
            continue

        rule_match = apply_vendor_rules(row, vendor_rules)
        if rule_match:
            acct = coa_lookup.get(rule_match["account_number"], {})
            cat_results[idx] = {
                "account_number": rule_match["account_number"],
                "account_name": acct.get("Account Name", rule_match["account_name"]),
                "confidence": rule_match["confidence"],
                "needs_review": "N",
                "categorization_notes": rule_match["notes"],
            }
            continue

        needs_claude.append((idx, row))

    if verbose:
        print(
            f"Pre-categorized {len(cat_results)} rows, "
            f"sending {len(needs_claude)} to Claude ({model}).",
            file=sys.stderr,
        )

    # Phase 2: Claude categorization in batches
    for start in range(0, len(needs_claude), BATCH_SIZE):
        batch = needs_claude[start:start + BATCH_SIZE]
        if verbose:
            end = min(start + BATCH_SIZE, len(needs_claude))
            print(f"  Batch {start + 1}–{end} of {len(needs_claude)}…", file=sys.stderr)

        claude_results = categorize_batch(client, batch, system_prompt, schema, model)

        for j, result in enumerate(claude_results):
            orig_idx, _ = batch[j]
            acct_num = result["account_number"]
            acct = coa_lookup.get(acct_num, {})
            confidence = result["confidence"]

            if review_threshold == "medium":
                flag = confidence in ("medium", "low") or acct_num == "UNKNOWN"
            else:
                flag = confidence == "low" or acct_num == "UNKNOWN"

            cat_results[orig_idx] = {
                "account_number": acct_num,
                "account_name": acct.get("Account Name", acct_num),
                "confidence": confidence,
                "needs_review": "Y" if flag else "N",
                "categorization_notes": result["notes"],
            }

    # Phase 3: merge and write outputs
    categorized_rows = []
    review_rows = []

    for idx, row in enumerate(rows):
        cat = cat_results.get(idx, {
            "account_number": "UNKNOWN",
            "account_name": "Unclassified",
            "confidence": "low",
            "needs_review": "Y",
            "categorization_notes": "No result returned",
        })
        merged = {
            **row,
            "coa_account_number": cat["account_number"],
            "coa_account_name": cat["account_name"],
            "confidence": cat["confidence"],
            "needs_review": cat["needs_review"],
            "categorization_notes": cat["categorization_notes"],
        }
        categorized_rows.append(merged)
        if cat["needs_review"] == "Y":
            review_rows.append(merged)

    def write_csv(data, path):
        if not data:
            Path(path).write_text("", encoding="utf-8")
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)

    write_csv(categorized_rows, output_categorized)
    write_csv(review_rows, output_review)

    if verbose:
        print(
            f"Done. {len(categorized_rows)} categorized, {len(review_rows)} need review.",
            file=sys.stderr,
        )
        print(f"Saved: {output_categorized}", file=sys.stderr)
        print(f"Saved: {output_review}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Categorization Agent")
    parser.add_argument("--normalized-file", required=True,
                        help="Path to normalized_transactions.csv from Agent 3")
    parser.add_argument("--coa-file", required=True,
                        help="Path to Final_COA_Import.csv from Agent 2")
    parser.add_argument("--client-rules", default=None,
                        help="Path to client_rules.json (optional vendor overrides)")
    parser.add_argument("--intake-file", default=None,
                        help="Path to intake_structured.json for business context (optional)")
    parser.add_argument("--output-categorized", default="/tmp/categorized_transactions.csv",
                        help="Output path for categorized_transactions.csv")
    parser.add_argument("--output-review", default="/tmp/review_required.csv",
                        help="Output path for review_required.csv")
    parser.add_argument("--review-threshold", choices=["low", "medium"], default="low",
                        help="Confidence floor for review queue: 'low' (default) or 'medium'")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Claude model (default: {DEFAULT_MODEL})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print progress to stderr")
    args = parser.parse_args()

    process(
        normalized_file=args.normalized_file,
        coa_file=args.coa_file,
        output_categorized=args.output_categorized,
        output_review=args.output_review,
        client_rules_file=args.client_rules,
        intake_file=args.intake_file,
        review_threshold=args.review_threshold,
        model=args.model,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
