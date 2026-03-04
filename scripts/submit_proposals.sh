#!/bin/sh

# Submit local Retreivr proposal JSONL files as GitHub Issues labeled "proposal".

set -u

OUTBOX_DEFAULT="${HOME}/.retreivr/community_outbox"
OUTBOX="${RETREIVR_OUTBOX:-$OUTBOX_DEFAULT}"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)

submitted_count=0
skipped_count=0
error_count=0

print_summary() {
  printf '\nSummary\n'
  printf 'submitted files: %s\n' "$submitted_count"
  printf 'skipped files: %s\n' "$skipped_count"
  printf 'errors: %s\n' "$error_count"
}

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI (gh) is not installed."
  echo "Install instructions:"
  echo "  macOS: brew install gh"
  echo "  Debian/Ubuntu: sudo apt install gh"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Error: GitHub CLI is not authenticated."
  echo "Run: gh auth login"
  exit 1
fi

REPO="${GITHUB_REPO:-}"
if [ -z "$REPO" ]; then
  ORIGIN_URL=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)
  if [ -n "$ORIGIN_URL" ]; then
    REPO=$(printf '%s' "$ORIGIN_URL" \
      | sed -e 's#^git@github.com:##' -e 's#^https://github.com/##' -e 's#\.git$##')
  fi
fi

if [ -z "$REPO" ]; then
  echo "Error: could not determine target repository."
  echo "Set GITHUB_REPO=owner/repo and try again."
  exit 1
fi

if [ ! -d "$OUTBOX" ]; then
  echo "Outbox directory does not exist: $OUTBOX"
  print_summary
  exit 0
fi

SUBMITTED_DIR="${OUTBOX}/submitted"
mkdir -p "$SUBMITTED_DIR"

found_any=0

for file in "$OUTBOX"/*.jsonl; do
  if [ ! -e "$file" ]; then
    break
  fi
  found_any=1

  if [ ! -f "$file" ] || [ ! -r "$file" ]; then
    echo "Skipping unreadable file: $file"
    skipped_count=$((skipped_count + 1))
    continue
  fi

  base_name=$(basename -- "$file")
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  title="Transport proposals ${timestamp}"

  tmp_body=$(mktemp)
  {
    echo "Automated proposal submission from Retreivr outbox."
    echo
    echo "Source file: ${base_name}"
    echo
    echo "\`\`\`jsonl"
    cat -- "$file"
    echo
    echo "\`\`\`"
  } >"$tmp_body"

  if gh issue create \
    --repo "$REPO" \
    --label "proposal" \
    --title "$title" \
    --body-file "$tmp_body" >/dev/null 2>&1; then
    mv -- "$file" "$SUBMITTED_DIR/$base_name"
    echo "Submitted: $base_name"
    submitted_count=$((submitted_count + 1))
  else
    echo "Error submitting: $base_name"
    error_count=$((error_count + 1))
  fi

  rm -f -- "$tmp_body"
done

if [ "$found_any" -eq 0 ]; then
  echo "No .jsonl files found in outbox: $OUTBOX"
fi

print_summary
exit 0
