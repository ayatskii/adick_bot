#!/bin/bash
# Production monitoring script

echo "📊 Production Monitoring Dashboard"
echo "=================================="

# Container status
echo "🐳 Container Status:"
docker-compose ps

echo ""

# Resource usage
echo "💾 Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

echo ""

# Volume usage
echo "💿 Volume Usage:"
docker system df -v | grep telegram-audio-bot

echo ""

# Recent logs
echo "📋 Recent Logs (last 20 lines):"
docker-compose logs --tail 20 telegram-audio-bot

echo ""

# Health status
echo "🏥 Health Status:"
./scripts/health-check.sh
