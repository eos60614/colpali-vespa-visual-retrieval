#!/bin/bash
# Cron wrapper for database sync with PDF processing
#
# What it does:
#   1. Syncs NEW/CHANGED structured records from PostgreSQL -> Vespa (procore_record)
#   2. Downloads NEW PDF files from S3
#   3. Processes PDFs with ColPali embeddings -> Vespa (pdf_page)
#
# Add to crontab:
#   0 */4 * * * /home/nirav60614/projects/colpali-vespa-visual-retrieval/scripts/sync_cron.sh
#
# Or for more frequent (every hour):
#   0 * * * * /home/nirav60614/projects/colpali-vespa-visual-retrieval/scripts/sync_cron.sh

set -e

# Configuration
PROJECT_DIR="/home/nirav60614/projects/colpali-vespa-visual-retrieval"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
LOCK_FILE="/tmp/procore-sync.lock"

# Load environment variables
set -a
source "$PROJECT_DIR/.env"
set +a

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Prevent overlapping runs (PDF processing can be slow due to model loading)
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE")
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync already running (PID: $pid), skipping"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi

# Create lock file
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

LOG_FILE="$LOG_DIR/sync_$(date '+%Y%m%d').log"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting sync..." | tee -a "$LOG_FILE"

# Activate venv and run sync
cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"

# Run incremental sync:
# - Syncs all structured data (change_orders, photos, projects, etc.)
# - Downloads new files from S3
# - Processes PDFs with ColPali for visual search
python scripts/sync_database.py --once \
    --download-files \
    --process-pdfs \
    --file-workers 2 \
    2>&1 | tee -a "$LOG_FILE"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync completed successfully" | tee -a "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync failed with exit code $exit_code" | tee -a "$LOG_FILE"
fi

exit $exit_code
