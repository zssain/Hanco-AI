#!/bin/bash
set -e

# If FIREBASE_SERVICE_ACCOUNT_JSON env var is set (as a JSON string),
# write it to a file so firebase-admin can use it.
if [ -n "$FIREBASE_SERVICE_ACCOUNT_JSON" ]; then
    echo "$FIREBASE_SERVICE_ACCOUNT_JSON" > /app/backend/firebase-key.json
    export GOOGLE_APPLICATION_CREDENTIALS=/app/backend/firebase-key.json
    echo "✅ Firebase service account written from env var"
fi

# Remove default nginx site if it exists
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

echo "🚀 Starting Dynamic Pricing Engine on port 8080..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
