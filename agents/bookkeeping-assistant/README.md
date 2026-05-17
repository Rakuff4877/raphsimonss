# Bookkeeping Automation Pipeline

**7-agent system that turns raw bank exports and intake transcripts into QuickBooks-ready financials**

## Problem

Bookkeeping for small businesses involves the same manual work every month: transcribing client intake meetings into account structures, downloading CSVs from five different sources, cleaning cryptic bank descriptions, categorizing hundreds of transactions, and preparing import files for QuickBooks. Each step requires domain knowledge and takes hours. Errors in early steps (like a wrong Chart of Accounts) cascade through the entire month's work.

## Solution

A pipeline of 7 specialized AI agents — each owning one stage of the bookkeeping workflow — that runs end-to-end from a new client intake meeting through to a QuickBooks-ready journal entry file. Claude Code orchestrates the pipeline; Python scripts handle data transformation; Google Drive (via MCP) is the shared document store across all agents.

## Agent Pipeline

| # | Agent | Input | Output |
|---|---|---|---|
| 0 | Onboarding | Client name | 15-folder Drive structure + client config |
| 1 | Intake Analysis | Zoom transcript | Structured JSON + COA template selection |
| 2 | COA Builder | Intake JSON + template | QuickBooks-importable Chart of Accounts |
| 3 | Bank Feed | Raw CSVs (bank/CC/Stripe/PayPal/Shopify) | Normalized transactions + QB bank feed |
| 4 | Categorization | Normalized transactions + COA | Categorized transactions + review queue |
| 5 | Reconciliation | Categorized transactions + bank PDFs | Reconciliation report *(in progress)* |
| 6 | Review | Review queue | Updated categorizations + vendor rules |
| 7 | Journal Entries | Approved transactions | Double-entry journal + QB import file |

## Architecture

- **Models**: `claude-opus-4-7` for Agents 1–2 (complex reasoning); `claude-sonnet-4-6` for Agents 3–4 (pattern matching, cost-sensitive)
- **Orchestration**: Claude Code CLI via `run.py`
- **Storage**: Google Drive (via MCP) — no files written locally beyond `/tmp`
- **Client config**: `config/clients/{slug}.json` stores all Drive folder IDs per client

## Setup

```bash
pip install -r requirements.txt

# Onboard a new client
python run.py --new-client "ClientName_2026"

# Switch active client
python run.py --set-client clientname_2026

# Run an agent
python run.py --agent intake
python run.py --agent coa
python run.py --agent bank-feed
python run.py --agent categorize
```

## Results

- Client onboarding reduced from hours of manual setup to a single pipeline run
- Bank feed normalization handles 5 source formats with zero manual column mapping
- ~80% of transactions categorized at high confidence; remainder routed to a human review queue
- Vendor rules persist across months — categorize a vendor once, it's automatic forever
- Each agent is independently runnable; a failure in one stage doesn't corrupt earlier outputs

> Real client configs (`config/clients/*.json`) and `config/active_client.json` are gitignored. Copy `config/clients/_template.json` to add a new client.
