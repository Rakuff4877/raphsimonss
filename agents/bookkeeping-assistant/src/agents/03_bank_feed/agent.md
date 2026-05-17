# Bank Feed / Transaction Normalization Agent

Agent 3 normalizes raw transaction CSVs from any source into a single unified schema,
then produces two outputs: a full normalized file and a QuickBooks-ready bank feed CSV.

## What This Agent Does

1. **Auto-detects the source format** from column headers and/or filename
2. **Normalizes** dates (→ YYYY-MM-DD), amounts (signed: negative = debit, positive = credit), and descriptions
3. **Detects internal transfers** — same absolute amount across two accounts within ±3 days
4. **Detects duplicates** — same date + description + amount within the same source file
5. **Enriches descriptions** via Claude (optional `--enrich` flag) — extracts clean vendor names from cryptic bank strings like "SQ *BLUE BOTTLE COF 855-700-6000"
6. Outputs `normalized_transactions.csv` (full data) and `qb_bank_feed.csv` (QB import format)

## Supported Source Types

| Type | Detection | Amount Convention |
|---|---|---|
| `bank` | Generic bank CSV; detected by column headers | Negative = debit, positive = credit |
| `credit_card` | CC CSV; detected by "type" column with SALE/RETURN values | Negative = charge, positive = credit/refund |
| `stripe` | Has "fee" + "net" + "id" columns, or filename contains "stripe" | Use Net amount (gross − fee); fee logged separately |
| `paypal` | Has "gross" + "fee" + "balance" columns, or filename contains "paypal" | Use Net amount; fee logged separately |
| `shopify` | Has "payout_id" or filename contains "shopify" | Use Net payout amount |

## Claude Enrichment Role (--enrich flag)

When enrichment is enabled, Claude receives batches of raw descriptions and returns:
- `vendor`: clean merchant/vendor name (e.g. "Starbucks" from "STARBUCKS #12345 SEATTLE WA")
- `description_clean`: human-readable description (e.g. "Coffee purchase" from "SQ *COFFEE SHOP 855-555-0000")

System prompt for enrichment:
> You are a bookkeeper's assistant. For each transaction description, extract the clean vendor name and a short, human-readable description. Remove reference numbers, phone numbers, location codes, and card suffixes. Return JSON with index, vendor, and description_clean.

## Normalized Output Schema (`normalized_transactions.csv`)

| Column | Description |
|---|---|
| `row_id` | Sequential integer ID |
| `source_file` | Original filename |
| `source_type` | bank / credit_card / stripe / paypal / shopify |
| `account_name` | Account label (e.g. "Chase Checking", "AMEX Card 1") |
| `date` | YYYY-MM-DD |
| `description` | Raw description from source |
| `description_clean` | Cleaned description (from Claude if enriched, else same as description) |
| `vendor` | Extracted vendor name (from Claude if enriched, else empty) |
| `amount` | Signed decimal — negative = money out, positive = money in |
| `currency` | Three-letter code (default: USD) |
| `transaction_id` | Source transaction ID if available |
| `is_transfer` | Y/N — flagged as likely internal transfer |
| `is_duplicate` | Y/N — flagged as likely duplicate |
| `notes` | Normalization notes (fee amount for Stripe/PayPal, etc.) |

## QB Bank Feed Output Schema (`qb_bank_feed.csv`)

```
Date,Description,Amount
2026-01-15,AMAZON.COM,-125.00
2026-01-16,Client Payment ACH,5000.00
```

Transfers and confirmed duplicates are excluded from the QB bank feed output.

## Usage

```bash
# Single file — auto-detect source type
python agents/03_bank_feed/processor.py \
  --input-file /tmp/chase_checking.csv \
  --account-name "Chase Checking"

# Single file — explicit source type
python agents/03_bank_feed/processor.py \
  --input-file /tmp/stripe_payouts.csv \
  --source-type stripe \
  --account-name "Stripe"

# Multiple files — outputs merged normalized CSV + QB feed
python agents/03_bank_feed/processor.py \
  --input-file /tmp/chase.csv --account-name "Chase Checking" \
  --input-file /tmp/amex1.csv --account-name "AMEX Card 1" \
  --input-file /tmp/stripe.csv --account-name "Stripe" \
  --output-normalized /tmp/normalized_transactions.csv \
  --output-qb /tmp/qb_bank_feed.csv \
  --enrich
```

## Claude Code Flow

1. Search `03_Raw_Documents/` subfolders for CSV files (Bank_Statements, Credit_Cards, Stripe, PayPal)
2. Download each CSV to `/tmp/raw/`
3. Run processor with all files, assigning account names from the COA
4. Upload `normalized_transactions.csv` → `04_Transactions/Normalized/`
5. Upload `qb_bank_feed.csv` → `04_Transactions/QB_Upload/`
