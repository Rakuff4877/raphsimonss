#!/usr/bin/env python3
"""
Intake Analysis Agent — processor.

Reads a Zoom transcript (from file or stdin), calls Claude to extract
structured business intelligence, and outputs JSON for Claude Code to
save to Google Drive.

Usage:
    python processor.py --transcript-file /tmp/transcript.txt
    cat transcript.txt | python processor.py
    python processor.py --transcript-file transcript.txt --model claude-opus-4-7

Output (stdout):
    JSON with two keys:
      "structured_data"  →  saved as intake_structured.json in Drive
      "summary_text"     →  saved as COA_Intake_Summary.txt in Drive
"""

import anthropic
import argparse
import json
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parent
SYSTEM_PROMPT = (AGENT_DIR / "agent.md").read_text()
DEFAULT_MODEL = "claude-opus-4-7"


def make_output_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "structured_data": {
                "type": "object",
                "properties": {
                    "client_name": {"type": "string"},
                    "entity_type": {
                        "type": "string",
                        "enum": ["LLC", "S-Corp", "C-Corp", "Sole Proprietor",
                                 "Partnership", "Non-Profit", "Unknown"],
                    },
                    "industry": {"type": "string"},
                    "accounting_method": {
                        "type": "string",
                        "enum": ["cash", "accrual", "unknown"],
                    },
                    "fiscal_year_start": {"type": "string"},
                    "business_description": {"type": "string"},
                    "revenue_streams": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "payment_processors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["name", "description", "payment_processors"],
                            "additionalProperties": False,
                        },
                    },
                    "expense_categories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["name", "description"],
                            "additionalProperties": False,
                        },
                    },
                    "payment_processors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "employees": {
                        "type": "object",
                        "properties": {
                            "count_estimate": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["W2", "1099", "both", "none", "unknown"],
                            },
                        },
                        "required": ["count_estimate", "type"],
                        "additionalProperties": False,
                    },
                    "payroll_provider": {"type": "string"},
                    "has_inventory": {"type": "boolean"},
                    "has_fixed_assets": {"type": "boolean"},
                    "has_loans": {"type": "boolean"},
                    "sales_tax_states": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "multicurrency": {"type": "boolean"},
                    "coa_template_recommendation": {
                        "type": "string",
                        "enum": [
                            "General_Service_Business_COA.csv",
                            "Retail_Business_COA.csv",
                            "Restaurant_COA.csv",
                            "Construction_COA.csv",
                            "Real_Estate_COA.csv",
                            "Medical_Practice_COA.csv",
                            "Non_Profit_COA.csv",
                            "E_Commerce_COA.csv",
                        ],
                    },
                    "special_accounts_needed": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "risks_and_complications": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "notes": {"type": "string"},
                },
                "required": [
                    "client_name", "entity_type", "industry", "accounting_method",
                    "fiscal_year_start", "business_description", "revenue_streams",
                    "expense_categories", "payment_processors", "employees",
                    "payroll_provider", "has_inventory", "has_fixed_assets",
                    "has_loans", "sales_tax_states", "multicurrency",
                    "coa_template_recommendation", "special_accounts_needed",
                    "risks_and_complications", "notes",
                ],
                "additionalProperties": False,
            },
            "summary_text": {"type": "string"},
        },
        "required": ["structured_data", "summary_text"],
        "additionalProperties": False,
    }


def analyze(transcript: str, model: str = DEFAULT_MODEL) -> dict:
    client = anthropic.Anthropic()
    schema = make_output_schema()

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{
            "role": "user",
            "content": (
                "Please analyze this client intake transcript and return the structured "
                "intake data plus a professional COA Intake Summary.\n\n"
                f"TRANSCRIPT:\n{transcript}"
            ),
        }],
    )

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Intake Analysis Agent")
    parser.add_argument(
        "--transcript-file",
        help="Path to transcript text file (default: read from stdin)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    if args.transcript_file:
        transcript = Path(args.transcript_file).read_text(encoding="utf-8")
    else:
        transcript = sys.stdin.read()

    if not transcript.strip():
        print("Error: transcript is empty.", file=sys.stderr)
        sys.exit(1)

    print("Analyzing intake transcript...", file=sys.stderr)
    result = analyze(transcript, model=args.model)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
