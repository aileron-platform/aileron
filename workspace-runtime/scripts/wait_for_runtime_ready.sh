#!/bin/sh
# Emit the ready message only after the Runtime health endpoint is healthy.

set -eu

until curl --fail --silent --output /dev/null --max-time 3 \
    http://127.0.0.1:3002/health; do
    sleep 1
done

echo "🎉 Workspace Runtime is ready!"
