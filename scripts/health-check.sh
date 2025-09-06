#!/bin/bash
# Production health check script

set -e

CONTAINER_NAME="telegram-audio-bot-telegram-audio-bot-1"
MAX_RETRIES=3
RETRY_INTERVAL=10

echo "🏥 Performing production health check..."

# Check if container is running
if ! docker ps --format "table {{.Names}}" | grep -q "telegram-audio-bot"; then
    echo "❌ Telegram Audio Bot container is not running"
    echo "📋 Available containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
    exit 1
fi

# Check container health status
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' $(docker ps -q --filter "name=telegram-audio-bot") 2>/dev/null || echo "unknown")

if [[ "$HEALTH_STATUS" == "healthy" ]]; then
    echo "✅ Container health check: HEALTHY"
elif [[ "$HEALTH_STATUS" == "unhealthy" ]]; then
    echo "❌ Container health check: UNHEALTHY"
    echo "📋 Recent health check logs:"
    docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' $(docker ps -q --filter "name=telegram-audio-bot") | tail -5
    exit 1
else
    echo "⚠️ Container health check: $HEALTH_STATUS"
fi

# Check resource usage
echo "📊 Resource usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" $(docker ps -q --filter "name=telegram-audio-bot")

# Check logs for errors
echo "📋 Recent application logs:"
docker-compose logs --tail 10 telegram-audio-bot

echo "✅ Production health check completed successfully!"
