#!/usr/bin/env python3
"""
Bank Feed / Transaction Normalization Agent — processor.

Normalizes raw transaction CSVs from any source into a unified schema,
detects transfers and duplicates, optionally enriches via Claude,
and outputs a normalized CSV + QuickBooks-ready bank feed CSV.

Usage:
    python processor.py --input-file chase.csv --account-name "Chase Checking"
    python processor.py \\
        --input-file chase.csv --account-name "Chase Checking" \\
        --input-file amex1.csv --account-name "AMEX Card 1" --source-type credit_card \\
        --input-file stripe.csv --account-name "Stripe" \\
        --output-normalized /tmp/normalized_transactions.csv \\
        --output-qb /tmp/qb_bank_feed.csv \\
        --enrich
"""

import argparse
import csv
import io
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BATCH_SIZE = 20
DEFAULT_MODEL = "claude-sonnet-4-6"

NORMALIZED_COLUMNS = [
    "row_id", "source_file", "source_type", "account_name",
    "date", "description", "description_clean", "vendor",
    "amount", "currency", "transaction_id",
    "is_transfer", "is_duplicate", "notes",
]

QB_COLUMNS = ["Date", "Description", "Amount"]


# ── Source type detection ──────────────────────────────────────────────────────

def detect_source_type(filename: str, headers: list[str]) -> str:
    lower_headers = {h.lower().strip() for h in headers}
    fname = Path(filename).name.lower()

    if "stripe" in fname:
        return "stripe"
    if "paypal" in fname:
        return "paypal"
    if "shopify" in fname:
        return "shopify"

    if "fee" in lower_headers and "net" in lower_headers and "id" in lower_headers:
        return "stripe"
    if "gross" in lower_headers and "fee" in lower_headers and "balance" in lower_headers:
        return "paypal"
    if "payout_id" in lower_headers:
        return "shopify"
    if any(h in lower_headers for h in ("type", "card no.", "card no")):
        if any(h in lower_headers for h in ("transaction date", "post date", "posted date")):
            return "credit_card"

    return "bank"


def detect_columns(headers: list[str], source_type: str) -> dict:
    """Map canonical keys to actual CSV column names."""
    lower_to_actual = {h.lower().strip(): h for h in headers}

    def find(*candidates) -> Optional[str]:
        for c in candidates:
            if c in lower_to_actual:
                return lower_to_actual[c]
        return None

    if source_type == "stripe":
        return {
            "date":    find("created (utc)", "created", "date"),
            "description": find("description", "statement descriptor"),
            "amount":  find("amount"),
            "fee":     find("fee"),
            "net":     find("net"),
            "id":      find("id", "balance transaction id"),
            "type":    find("type"),
        }
    if source_type == "paypal":
        return {
            "date":    find("date"),
            "description": find("item title", "subject", "name", "description"),
            "gross":   find("gross"),
            "fee":     find("fee"),
            "net":     find("net"),
            "id":      find("transaction id"),
            "type":    find("type"),
            "status":  find("status"),
        }
    if source_type == "shopify":
        return {
            "date":    find("payout date", "date"),
            "description": find("description", "type"),
            "amount":  find("amount", "net"),
            "fee":     find("fee"),
            "id":      find("payout_id", "id"),
        }
    if source_type == "credit_card":
        return {
            "date":    find("transaction date", "date", "trans. date", "posted date"),
            "description": find("description", "merchant", "payee", "memo"),
            "amount":  find("amount"),
            "type":    find("type"),
            "id":      find("reference", "transaction id"),
            "debit":   find("debit"),
            "credit":  find("credit"),
        }
    # bank (default)
    return {
        "date":    find("date", "transaction date", "posted date", "trans. date"),
        "description": find("description", "narrative", "memo", "details", "payee"),
        "amount":  find("amount", "transaction amount", "value"),
        "debit":   find("debit", "withdrawals", "withdrawal"),
        "credit":  find("credit", "deposits", "deposit"),
        "balance": find("balance", "running bal.", "running balance"),
        "id":      find("check number", "transaction id", "reference"),
    }


# ── Date normalisation ─────────────────────────────────────────────────────────

_DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y",
    "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%Y/%m/%d",
    "%m-%d-%Y", "%d-%m-%Y",
]


def normalize_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw  # return as-is if unrecognised


# ── Amount normalisation ───────────────────────────────────────────────────────

def _parse_decimal(s: str) -> float:
    if not s:
        return 0.0
    return float(re.sub(r"[^\d.\-\+]", "", s.replace(",", "")) or "0")


def normalize_amount(row: dict, col_map: dict, source_type: str) -> tuple[float, str]:
    """Returns (amount, notes). Amount: negative = money out, positive = money in."""
    notes = ""

    if source_type in ("stripe", "paypal"):
        gross = _parse_decimal(row.get(col_map.get("gross") or col_map.get("amount", ""), ""))
        fee   = _parse_decimal(row.get(col_map.get("fee", ""), ""))
        net   = _parse_decimal(row.get(col_map.get("net", ""), ""))
        if net != 0:
            amount = net / 100 if abs(net) > 1000 and source_type == "stripe" else net
        elif gross != 0:
            amount = gross - abs(fee)
        else:
            amount = 0.0
        if fee != 0:
            notes = f"fee={abs(fee):.2f}"
        return amount, notes

    if source_type == "shopify":
        amount = _parse_decimal(row.get(col_map.get("amount", ""), ""))
        fee = _parse_decimal(row.get(col_map.get("fee", ""), ""))
        if fee:
            notes = f"fee={abs(fee):.2f}"
        return amount, notes

    # bank or credit_card — try single amount column first
    amount_col = col_map.get("amount")
    debit_col  = col_map.get("debit")
    credit_col = col_map.get("credit")

    if amount_col and row.get(amount_col, "").strip():
        return _parse_decimal(row[amount_col]), notes

    # Split debit/credit columns
    debit  = _parse_decimal(row.get(debit_col or "", "") or "0")
    credit = _parse_decimal(row.get(credit_col or "", "") or "0")
    if debit != 0:
        return -abs(debit), notes
    if credit != 0:
        return abs(credit), notes
    return 0.0, notes


# ── Row normalisation ──────────────────────────────────────────────────────────

def normalize_rows(
    filepath: str,
    account_name: str,
    source_type: Optional[str] = None,
) -> list[dict]:
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    if not raw_rows:
        return []

    headers = list(raw_rows[0].keys())
    if source_type is None:
        source_type = detect_source_type(filepath, headers)

    col_map = detect_columns(headers, source_type)
    source_file = Path(filepath).name
    results = []

    for raw in raw_rows:
        date_raw = raw.get(col_map.get("date", "") or "", "").strip()
        if not date_raw:
            continue  # skip blank rows

        desc_col = col_map.get("description", "")
        description = raw.get(desc_col or "", "").strip() if desc_col else ""

        amount, notes = normalize_amount(raw, col_map, source_type)

        # PayPal: skip failed/pending transactions
        if source_type == "paypal":
            status_col = col_map.get("status", "")
            if status_col and raw.get(status_col, "").strip().lower() not in ("completed", ""):
                continue

        id_col = col_map.get("id", "")
        transaction_id = raw.get(id_col or "", "").strip() if id_col else ""

        results.append({
            "source_file":      source_file,
            "source_type":      source_type,
            "account_name":     account_name,
            "date":             normalize_date(date_raw),
            "description":      description,
            "description_clean": description,
            "vendor":           "",
            "amount":           round(amount, 2),
            "currency":         "USD",
            "transaction_id":   transaction_id,
            "is_transfer":      "N",
            "is_duplicate":     "N",
            "notes":            notes,
        })

    return results


# ── Transfer and duplicate detection ──────────────────────────────────────────

def detect_transfers(records: list[dict]) -> None:
    """Flag records that appear to be internal transfers (same amount, different account, ±3 days)."""
    by_amount: dict[float, list[int]] = {}
    for i, r in enumerate(records):
        key = abs(r["amount"])
        by_amount.setdefault(key, []).append(i)

    for idxs in by_amount.values():
        if len(idxs) < 2:
            continue
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                a, b = records[idxs[i]], records[idxs[j]]
                if a["account_name"] == b["account_name"]:
                    continue
                # Opposite signs required for a true transfer
                if (a["amount"] > 0) == (b["amount"] > 0):
                    continue
                try:
                    da = datetime.strptime(a["date"], "%Y-%m-%d")
                    db = datetime.strptime(b["date"], "%Y-%m-%d")
                    if abs((da - db).days) <= 3:
                        records[idxs[i]]["is_transfer"] = "Y"
                        records[idxs[j]]["is_transfer"] = "Y"
                except ValueError:
                    pass


def detect_duplicates(records: list[dict]) -> None:
    """Flag duplicate rows within the same source file (same date + description + amount)."""
    seen: set[tuple] = set()
    for r in records:
        key = (r["source_file"], r["date"], r["description"], r["amount"])
        if key in seen:
            r["is_duplicate"] = "Y"
        else:
            seen.add(key)


# ── Claude enrichment ──────────────────────────────────────────────────────────

def enrich_descriptions(records: list[dict], model: str = DEFAULT_MODEL) -> None:
    """Batch-enrich descriptions with clean vendor names via Claude."""
    import anthropic

    client = anthropic.Anthropic()
    system = (
        "You are a bookkeeper's assistant. For each transaction description, "
        "extract the clean vendor/merchant name and write a short human-readable description. "
        "Remove reference numbers, phone numbers, card suffixes, and location codes. "
        "Return JSON with 'results': list of {index, vendor, description_clean}."
    )
    schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "vendor": {"type": "string"},
                        "description_clean": {"type": "string"},
                    },
                    "required": ["index", "vendor", "description_clean"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["results"],
        "additionalProperties": False,
    }

    total = len(records)
    for start in range(0, total, BATCH_SIZE):
        batch = records[start: start + BATCH_SIZE]
        items = [{"index": i, "description": r["description"]} for i, r in enumerate(batch)]
        print(f"  Enriching descriptions {start+1}–{min(start+BATCH_SIZE, total)} of {total}…", file=sys.stderr)

        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": json.dumps(items)}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        for result in json.loads(text)["results"]:
            idx = result["index"]
            if idx < len(batch):
                batch[idx]["vendor"] = result["vendor"]
                batch[idx]["description_clean"] = result["description_clean"]


# ── CSV output ─────────────────────────────────────────────────────────────────

def write_normalized_csv(records: list[dict], path: Optional[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=NORMALIZED_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for i, r in enumerate(records, 1):
        r["row_id"] = i
        writer.writerow(r)
    content = buf.getvalue()
    if path:
        Path(path).write_text(content, encoding="utf-8")
    return content


def write_qb_feed_csv(records: list[dict], path: Optional[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=QB_COLUMNS)
    writer.writeheader()
    for r in records:
        if r["is_transfer"] == "Y" or r["is_duplicate"] == "Y":
            continue
        writer.writerow({
            "Date": r["date"],
            "Description": r["description_clean"] or r["description"],
            "Amount": r["amount"],
        })
    content = buf.getvalue()
    if path:
        Path(path).write_text(content, encoding="utf-8")
    return content


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Bank Feed / Transaction Normalization Agent")
    parser.add_argument("--input-file", action="append", dest="input_files", metavar="FILE",
                        required=True, help="Input CSV file (repeat for multiple files)")
    parser.add_argument("--account-name", action="append", dest="account_names", metavar="NAME",
                        required=True, help="Account name for this file (must match --input-file order)")
    parser.add_argument("--source-type", action="append", dest="source_types", metavar="TYPE",
                        help="Override source type (bank/credit_card/stripe/paypal/shopify). "
                             "Repeat to match --input-file order. Defaults to auto-detect.")
    parser.add_argument("--output-normalized", default=None,
                        help="Path for normalized_transactions.csv (default: stdout)")
    parser.add_argument("--output-qb", default=None,
                        help="Path for qb_bank_feed.csv")
    parser.add_argument("--enrich", action="store_true",
                        help="Call Claude API to clean descriptions and extract vendor names")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if len(args.input_files) != len(args.account_names):
        print("Error: --input-file and --account-name must be paired.", file=sys.stderr)
        sys.exit(1)

    source_types = args.source_types or []
    all_records: list[dict] = []

    for i, (fpath, acct) in enumerate(zip(args.input_files, args.account_names)):
        stype = source_types[i] if i < len(source_types) else None
        print(f"Processing: {fpath} ({acct})…", file=sys.stderr)
        records = normalize_rows(fpath, acct, stype)
        print(f"  → {len(records)} transactions", file=sys.stderr)
        all_records.extend(records)

    print(f"Total: {len(all_records)} transactions across {len(args.input_files)} file(s).", file=sys.stderr)

    detect_transfers(all_records)
    transfers = sum(1 for r in all_records if r["is_transfer"] == "Y")
    if transfers:
        print(f"  Flagged {transfers} transfer records.", file=sys.stderr)

    detect_duplicates(all_records)
    dupes = sum(1 for r in all_records if r["is_duplicate"] == "Y")
    if dupes:
        print(f"  Flagged {dupes} duplicate records.", file=sys.stderr)

    if args.enrich:
        print("Enriching descriptions with Claude…", file=sys.stderr)
        enrich_descriptions(all_records, model=args.model)

    norm_csv = write_normalized_csv(all_records, args.output_normalized)
    qb_csv   = write_qb_feed_csv(all_records, args.output_qb)

    if args.output_normalized:
        print(f"Normalized CSV → {args.output_normalized}", file=sys.stderr)
    else:
        print(norm_csv, end="")

    if args.output_qb:
        qb_count = sum(1 for r in all_records if r["is_transfer"] == "N" and r["is_duplicate"] == "N")
        print(f"QB Feed CSV   → {args.output_qb} ({qb_count} transactions)", file=sys.stderr)


if __name__ == "__main__":
    main()
