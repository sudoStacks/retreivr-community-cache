#!/bin/sh

# Install a cron job for automated proposal submission.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SUBMIT_SCRIPT="${SCRIPT_DIR}/submit_proposals.sh"

if [ ! -f "$SUBMIT_SCRIPT" ]; then
  echo "Error: submit script not found at $SUBMIT_SCRIPT"
  exit 1
fi

if ! command -v crontab >/dev/null 2>&1; then
  echo "Error: crontab command not found on this system."
  exit 1
fi

if ! command -v sh >/dev/null 2>&1; then
  echo "Error: shell command not available."
  exit 1
fi

echo "Choose schedule for automated proposal submission:"
echo "1) Hourly    (0 * * * *)"
echo "2) Daily     (0 2 * * *)"
echo "3) Custom cron expression"
printf "Selection [1-3]: "
read -r selection

cron_expr=""
case "$selection" in
  1|"")
    cron_expr="0 * * * *"
    ;;
  2)
    cron_expr="0 2 * * *"
    ;;
  3)
    printf "Enter cron expression (5 fields): "
    read -r cron_expr
    set -- $cron_expr
    if [ "$#" -ne 5 ]; then
      echo "Error: cron expression must have exactly 5 fields."
      exit 1
    fi
    ;;
  *)
    echo "Error: invalid selection."
    exit 1
    ;;
esac

cron_cmd="/bin/sh \"$SUBMIT_SCRIPT\""
new_line="$cron_expr $cron_cmd"

tmp_cron=$(mktemp)

if crontab -l >/dev/null 2>&1; then
  crontab -l | grep -F -v "$SUBMIT_SCRIPT" >"$tmp_cron" || true
else
  : >"$tmp_cron"
fi

echo "$new_line" >>"$tmp_cron"

if crontab "$tmp_cron"; then
  echo "Installed cron schedule:"
  echo "  $new_line"
else
  echo "Error: failed to install crontab entry."
  rm -f -- "$tmp_cron"
  exit 1
fi

rm -f -- "$tmp_cron"
exit 0
