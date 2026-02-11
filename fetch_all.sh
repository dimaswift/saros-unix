#!/usr/bin/env bash
set -euo pipefail

START=${1:-1}
END=${2:-180}

success=0
failed=0
skipped=0

for i in $(seq "$START" "$END"); do
    if [ -f "$i/eclipses.jsonl" ] && [ -f "$i/saros.json" ]; then
        echo "Skipping Saros $i (already exists)"
        ((skipped++)) || true
        continue
    fi

    echo -n "Saros $i ... "
    if python3 parse_saros.py "$i" 2>&1 | tail -1; then
        ((success++)) || true
    else
        echo "FAILED: Saros $i" >&2
        ((failed++)) || true
    fi
done

echo ""
echo "Done: $success succeeded, $failed failed, $skipped skipped"
