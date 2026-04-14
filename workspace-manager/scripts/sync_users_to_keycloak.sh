#!/bin/bash
# Sync existing users to Keycloak
# This script helps migrate existing users to Keycloak before removing local auth

set -e

# Configuration
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-aileron}"
KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-admin-cli}"
KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN_USER:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-admin}"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-aileron}"
DB_USER="${DB_USER:-postgres}"

echo "🔄 Syncing existing users to Keycloak..."
echo "   Keycloak: $KEYCLOAK_URL"
echo "   Realm: $KEYCLOAK_REALM"
echo "   Database: $DB_NAME"
echo ""

# Get admin access token
echo "1️⃣  Getting Keycloak admin access token..."
ACCESS_TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$KEYCLOAK_CLIENT_ID" \
  -d "username=$KEYCLOAK_ADMIN_USER" \
  -d "password=$KEYCLOAK_ADMIN_PASSWORD" \
  -d "grant_type=password" | jq -r '.access_token')

if [ "$ACCESS_TOKEN" == "null" ] || [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ Failed to get access token. Please check your Keycloak admin credentials."
  exit 1
fi

echo "✅ Access token obtained"
echo ""

# Get users from database without keycloak_id
echo "2️⃣  Finding users without Keycloak ID..."
USERS_WITHOUT_KEYCLOAK=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
  SELECT id, email, username, display_name
  FROM users
  WHERE keycloak_id IS NULL
  AND email IS NOT NULL;
")

if [ -z "$USERS_WITHOUT_KEYCLOAK" ]; then
  echo "✅ All users already have Keycloak IDs!"
  exit 0
fi

USER_COUNT=$(echo "$USERS_WITHOUT_KEYCLOAK" | wc -l | tr -d ' ')
echo "   Found $USER_COUNT users without Keycloak ID"
echo ""

# Sync each user to Keycloak
echo "3️⃣  Syncing users to Keycloak..."
echo "$USERS_WITHOUT_KEYCLOAK" | while IFS='|' read -r USER_ID EMAIL USERNAME DISPLAY_NAME; do
  # Trim whitespace
  USER_ID=$(echo "$USER_ID" | xargs)
  EMAIL=$(echo "$EMAIL" | xargs)
  USERNAME=$(echo "$USERNAME" | xargs)
  DISPLAY_NAME=$(echo "$DISPLAY_NAME" | xargs)

  echo "   📧 Processing: $EMAIL ($USERNAME)"

  # Create user in Keycloak
  USER_CREATION_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/admin/realms/$KEYCLOAK_REALM/users" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"username\": \"$USERNAME\",
      \"email\": \"$EMAIL\",
      \"enabled\": true,
      \"emailVerified\": true,
      \"attributes\": {
        \"localUserId\": \"$USER_ID\"
      }
    }")

  # Get the created user's ID from Keycloak
  sleep 1  # Give Keycloak a moment to process
  KEYCLOAK_USER_ID=$(curl -s "$KEYCLOAK_URL/admin/realms/$KEYCLOAK_REALM/users?username=$USERNAME" \
    -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.[0].id')

  if [ "$KEYCLOAK_USER_ID" == "null" ] || [ -z "$KEYCLOAK_USER_ID" ]; then
    echo "   ❌ Failed to create user in Keycloak"
    continue
  fi

  # Update database with keycloak_id
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
    "UPDATE users SET keycloak_id = '$KEYCLOAK_USER_ID' WHERE id = '$USER_ID';"

  echo "   ✅ Synced: $EMAIL -> Keycloak ID: $KEYCLOAK_USER_ID"
  echo ""
done

echo "✅ User sync completed!"
echo ""
echo "⚠️  IMPORTANT: Inform users that they need to:"
echo "   1. Go to Keycloak to set their password"
echo "   2. Or use the 'Forgot Password' feature"
echo ""
echo "🔑 Keycloak URL: $KEYCLOAK_URL/realms/$KEYCLOAK_REALM/account"
