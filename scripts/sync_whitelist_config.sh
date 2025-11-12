#!/bin/bash
# Sync whitelist_config.py from Docker volume to project directory
# This script should be run when Docker container stops

set -e

CONTAINER_NAME="adick_bot-telegram-audio-bot-1"
CONFIG_SOURCE="/app/config/whitelist_config.py"
CONFIG_DEST="./whitelist_config.py"

echo "🔄 Syncing whitelist_config.py from Docker container..."

# Check if container exists and is running
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    # Check if container is running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "⚠️  Container is still running. Stopping it first..."
        docker stop "${CONTAINER_NAME}" || true
    fi
    
    # Copy config from container
    if docker cp "${CONTAINER_NAME}:${CONFIG_SOURCE}" "${CONFIG_DEST}" 2>/dev/null; then
        echo "✅ Successfully synced whitelist_config.py to project directory"
        echo "📝 File location: ${CONFIG_DEST}"
    else
        echo "⚠️  Could not copy from container (file may not exist in volume)"
        echo "ℹ️  This is normal if no users were added via Docker"
    fi
else
    echo "⚠️  Container not found: ${CONTAINER_NAME}"
    echo "ℹ️  Trying to find container with different name..."
    
    # Try to find any container with the bot
    BOT_CONTAINER=$(docker ps -a --format '{{.Names}}' | grep -i "telegram.*bot\|adick.*bot" | head -1)
    if [ -n "${BOT_CONTAINER}" ]; then
        echo "📦 Found container: ${BOT_CONTAINER}"
        if docker cp "${BOT_CONTAINER}:${CONFIG_SOURCE}" "${CONFIG_DEST}" 2>/dev/null; then
            echo "✅ Successfully synced whitelist_config.py"
        else
            echo "⚠️  Could not copy from container"
        fi
    else
        echo "❌ No bot container found"
    fi
fi

