#!/usr/bin/env bash
set -euo pipefail

# Fetch all lunar Saros series (1-180) from NASA.
# Usage: ./lunar/fetch_all.sh [START [END]]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

START=${1:-1}
END=${2:-180}

success=0
failed=0
skipped=0

for i in $(seq "$START" "$END"); do
    if [ -f "$SCRIPT_DIR/$i/eclipses.jsonl" ] && [ -f "$SCRIPT_DIR/$i/saros.json" ]; then
        echo "Skipping Lunar Saros $i (already exists)"
        ((skipped++)) || true
        continue
    fi

    echo -n "Lunar Saros $i ... "
    if python3 "$ROOT_DIR/parse_lunar_saros.py" "$i" 2>&1 | tail -1; then
        ((success++)) || true
    else
        echo "FAILED: Lunar Saros $i" >&2
        ((failed++)) || true
    fi
done

echo ""
echo "Done: $success succeeded, $failed failed, $skipped skipped"
