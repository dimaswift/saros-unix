#!/usr/bin/env bash
set -euo pipefail

# Fetch all Saros series (solar and/or lunar) from NASA.
# Usage: ./fetch_all.sh [solar|lunar|both] [START [END]]
#   kind   : solar, lunar, or both (default: both)
#   START  : first Saros number (default: 1)
#   END    : last  Saros number (default: 180)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

KIND=${1:-both}
START=${2:-1}
END=${3:-180}

case "$KIND" in
    solar)
        bash "$SCRIPT_DIR/solar/fetch_all.sh" "$START" "$END"
        ;;
    lunar)
        bash "$SCRIPT_DIR/lunar/fetch_all.sh" "$START" "$END"
        ;;
    both)
        echo "=== Solar ==="
        bash "$SCRIPT_DIR/solar/fetch_all.sh" "$START" "$END"
        echo ""
        echo "=== Lunar ==="
        bash "$SCRIPT_DIR/lunar/fetch_all.sh" "$START" "$END"
        ;;
    *)
        echo "Usage: $0 [solar|lunar|both] [START [END]]" >&2
        exit 1
        ;;
esac
