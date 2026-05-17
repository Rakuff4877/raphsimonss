#!/bin/bash
# Pre-commit hook: blocks commits that look like they contain secrets.
# Install: cp scripts/check_secrets.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

PATTERNS=(
  'sk-[a-zA-Z0-9]{20,}'
  'ntn_[a-zA-Z0-9]+'
  'Bearer [a-zA-Z0-9\-_.]+'
  'NOTION_TOKEN\s*=\s*[^y]'
  'secret_[a-zA-Z0-9]+'
  'api_key\s*=\s*["\x27][^"\x27]'
)

STAGED=$(git diff --cached --name-only)

for file in $STAGED; do
  [ -f "$file" ] || continue
  for pattern in "${PATTERNS[@]}"; do
    if git show ":$file" | grep -qE "$pattern"; then
      echo "ERROR: Possible secret found in $file (matched: $pattern)"
      echo "Remove the secret and use an environment variable instead."
      exit 1
    fi
  done
done

exit 0
