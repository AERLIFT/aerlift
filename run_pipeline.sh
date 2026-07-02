#!/usr/bin/env bash
set -euo pipefail

# ── config ────────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$REPO_DIR/logs/runs"
LOCK_FILE="/tmp/aerlift_pipeline.lock"
CORES="${AERLIFT_CORES:-2}"

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

echo "[$(date)] Starting AERLIFT pipeline (cores=$CORES)"
echo "[$(date)] Log: $LOG"

# ── run ───────────────────────────────────────────────────────────────────────
cd "$REPO_DIR"

docker compose run --rm aerlift \
    snakemake \
    --snakefile workflow/snakefile \
    --cores "$CORES"

echo "[$(date)] Pipeline complete."
