#!/bin/bash
# PostgreSQL Backup Cron Script
# 
# Add to crontab (runs daily at 3 AM):
#   0 3 * * * /path/to/scripts/backup_cron.sh >> /var/log/backup.log 2>&1
#
# For production with S3:
#   0 3 * * * /path/to/scripts/backup_cron.sh --s3 my-backup-bucket >> /var/log/backup.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Run backup via Docker
docker-compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    | gzip > "$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S).sql.gz"

# Alternative: Run Python backup script
# python "$SCRIPT_DIR/backup_database.py" "$@"

echo "Backup completed at $(date)"
