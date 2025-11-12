#!/bin/bash
# Docker shutdown hook to sync whitelist_config.py from volume to project
# Add this to docker-compose.yml or run manually after docker-compose down

set -e

VOLUME_NAME="adick_bot_whitelist_config"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/whitelist_config.py"

echo "🔄 Syncing whitelist_config.py from Docker volume..."

# Check if volume exists
if ! docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1; then
    echo "⚠️  Volume ${VOLUME_NAME} not found. Nothing to sync."
    exit 0
fi

# Create temporary container to access volume
TEMP_CONTAINER="temp_sync_$(date +%s)"

# Extract config from volume
if docker run --rm \
    --name "${TEMP_CONTAINER}" \
    -v "${VOLUME_NAME}:/data" \
    alpine:latest \
    test -f /data/whitelist_config.py 2>/dev/null; then
    
    # Copy file from volume
    docker run --rm \
        --name "${TEMP_CONTAINER}" \
        -v "${VOLUME_NAME}:/data" \
        -v "${PROJECT_ROOT}:/output" \
        alpine:latest \
        sh -c "cp /data/whitelist_config.py /output/whitelist_config.py 2>/dev/null || exit 0"
    
    if [ -f "${CONFIG_FILE}" ]; then
        echo "✅ Successfully synced whitelist_config.py"
        echo "📝 Location: ${CONFIG_FILE}"
    else
        echo "⚠️  File not found in volume (may not have been modified)"
    fi
else
    echo "⚠️  whitelist_config.py not found in volume"
fi

