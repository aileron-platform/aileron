#!/bin/bash
# Backup users table data before removing local authentication
# This script creates a SQL dump of the users table for safety

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-aileron}"
DB_USER="${DB_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/users_backup_${TIMESTAMP}.sql"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "🔄 Backing up users table..."
echo "   Database: $DB_NAME"
echo "   Host: $DB_HOST:$DB_PORT"
echo "   Backup file: $BACKUP_FILE"

# Backup users table structure and data
pg_dump -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -t "users" \
        --no-owner \
        --no-acl \
        > "$BACKUP_FILE"

echo "✅ Backup completed successfully!"
echo "   Backup saved to: $BACKUP_FILE"
echo ""
echo "⚠️  IMPORTANT: Store this backup in a safe location!"
echo "   You may need it to migrate users to Keycloak."
