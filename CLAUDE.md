# Agent Portfolio

A portfolio of AI/LLM agent case studies, with Notion as the public-facing front-end and this repo as the source of truth for agent code.

## Structure

```
agent-portfolio/
├── agents/
│   └── <agent-name>/
│       ├── case_study.yaml   # metadata that syncs to Notion
│       ├── README.md         # human-readable case study
│       └── src/              # actual agent code
├── sync/
│   ├── notion_sync.py        # pushes case_study.yaml → Notion DB
│   └── requirements.txt
├── template/
│   └── case_study.yaml       # copy this when adding a new agent
└── scripts/
    └── check_secrets.sh      # install as pre-commit hook
```

## Adding a new agent

1. Copy `template/case_study.yaml` → `agents/<your-agent>/case_study.yaml`
2. Fill in all fields
3. Add agent code under `agents/<your-agent>/src/`
4. Run `python sync/notion_sync.py` to push to Notion

## Syncing to Notion

```bash
cd sync
pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in your credentials
python notion_sync.py
```

The script creates new Notion pages for new agents and updates existing ones — no duplicates.

## Secret hygiene — IMPORTANT

- **Never commit `.env`** — it is in `.gitignore`
- All credentials must come from environment variables
- Install the pre-commit hook to catch accidental leaks:
  ```bash
  cp scripts/check_secrets.sh .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit
  ```
- `.env.example` documents required variables with placeholder values and is safe to commit
