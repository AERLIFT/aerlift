#!/usr/bin/env bash
set -euo pipefail

# ── config ────────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$REPO_DIR/logs/runs"
LOCK_FILE="/tmp/aerlift_pipeline.lock"
CORES="${AERLIFT_CORES:-2}"
CONFIG="${AERLIFT_CONFIG:-config/config.yaml}"

# ── parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config|-c) CONFIG="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# ── lock: prevent overlapping cron runs ───────────────────────────────────────
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "[$(date)] Pipeline already running (PID $pid). Exiting." >&2
        exit 1
    fi
    # stale lock — previous run crashed without cleanup
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ── logging ───────────────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "[$(date)] Starting AERLIFT pipeline (cores=$CORES, config=$CONFIG)"
echo "[$(date)] Log: $LOG"

# ── run ───────────────────────────────────────────────────────────────────────
cd "$REPO_DIR"

docker compose run --rm aerlift \
    snakemake \
    --snakefile workflow/snakefile \
    --configfile "$CONFIG" \
    --cores "$CORES"

echo "[$(date)] Pipeline complete."
