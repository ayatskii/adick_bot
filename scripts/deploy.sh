#!/bin/bash
# Production deployment script

set -e

echo "🚀 Deploying Telegram Audio Bot to Production..."

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    echo "❌ .env file not found. Please create it with your API keys"
    exit 1
fi

# Load environment variables
source .env

# Validate required environment variables
echo "🔍 Validating environment variables..."
required_vars=("TELEGRAM_BOT_TOKEN" "ELEVENLABS_API_KEY" "OPENAI_API_KEY")

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "❌ Required environment variable $var is not set"
        exit 1
    fi
done

echo "✅ Environment variables validated"

# Stop existing containers gracefully
echo "🛑 Stopping existing containers..."
docker-compose down --timeout 30

# Build and start the production service
echo "🏗️ Building and starting production service..."
docker-compose up -d --build

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
timeout=120
elapsed=0

while [ $elapsed -lt $timeout ]; do
    if docker-compose ps | grep -q "Up"; then
        echo "✅ Service is running!"
        break
    fi
    
    echo "⏳ Waiting for service... ($elapsed/$timeout seconds)"
    sleep 5
    elapsed=$((elapsed + 5))
done

if [ $elapsed -ge $timeout ]; then
    echo "❌ Service failed to start within $timeout seconds"
    echo "📋 Container status:"
    docker-compose ps
    echo "📋 Container logs:"
    docker-compose logs --tail 50
    exit 1
fi

# Show final status
echo "📋 Production deployment status:"
docker-compose ps

echo "📊 Resource usage:"
docker stats --no-stream adick_bot_telegram-audio-bot_1 2>/dev/null || echo "Container stats not available yet"

echo "🎉 Production deployment completed successfully!"
echo "📱 Bot is now running and processing audio messages"
