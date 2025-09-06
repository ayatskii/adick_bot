#!/bin/bash
# Production build script for Telegram Audio Bot

set -e

echo "🐳 Building Production Telegram Audio Bot..."

# Configuration
IMAGE_NAME="telegram-audio-bot"
TAG="latest"

# Build the production image
echo "📦 Building optimized production image..."
docker build \
    -t "${IMAGE_NAME}:${TAG}" \
    --target runtime \
    --no-cache \
    .

# Verify the build
if docker inspect "${IMAGE_NAME}:${TAG}" > /dev/null 2>&1; then
    echo "✅ Production image built successfully: ${IMAGE_NAME}:${TAG}"
    
    # Show image size
    SIZE=$(docker images "${IMAGE_NAME}:${TAG}" --format "table {{.Size}}" | tail -n +2)
    echo "📊 Final image size: ${SIZE}"
    
    # Show image layers
    echo "🔍 Image layers:"
    docker history "${IMAGE_NAME}:${TAG}" --format "table {{.CreatedBy}}\t{{.Size}}" | head -10
    
else
    echo "❌ Production image build failed"
    exit 1
fi

echo "🎉 Production build completed successfully!"
