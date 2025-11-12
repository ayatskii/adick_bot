# Telegram Audio Bot Production Makefile

.PHONY: help setup build deploy start stop restart logs health monitor clean clean-all

# Default target
help:
	@echo "🤖 Telegram Audio Bot Production Commands"
	@echo "========================================"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  setup     - Initial setup (create .env, make scripts executable)"
	@echo "  build     - Build production Docker image"
	@echo "  deploy    - Deploy to production (build + start)"
	@echo ""
	@echo "Service Management:"
	@echo "  start     - Start the bot service"
	@echo "  stop      - Stop the bot service"
	@echo "  restart   - Restart the bot service"
	@echo ""
	@echo "Monitoring & Logs:"
	@echo "  logs      - Show real-time logs"
	@echo "  health    - Run health check"
	@echo "  monitor   - Show monitoring dashboard"
	@echo ""
	@echo "Whitelist Management:"
	@echo "  sync-config - Sync whitelist_config.py from Docker volume to project"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean     - Clean up containers and images"
	@echo "  clean-all - Clean up everything including volumes (DESTRUCTIVE)"
	@echo ""

setup:
	@./scripts/setup.sh

build:
	@./scripts/build.sh

deploy:
	@./scripts/deploy.sh

start:
	@echo "🚀 Starting Telegram Audio Bot..."
	@docker-compose up -d

stop:
	@echo "🛑 Stopping Telegram Audio Bot..."
	@docker-compose down
	@echo "🔄 Syncing whitelist_config.py from Docker volume..."
	@python scripts/sync_whitelist_config.py || bash scripts/sync_whitelist_config.sh || echo "⚠️  Sync skipped (not critical)"

restart:
	@echo "🔄 Restarting Telegram Audio Bot..."
	@docker-compose restart

logs:
	@echo "📋 Showing real-time logs (Ctrl+C to exit)..."
	@docker-compose logs -f telegram-audio-bot

health:
	@./scripts/health-check.sh

monitor:
	@./scripts/monitor.sh

clean:
	@echo "🧹 Cleaning up containers and images..."
	@docker-compose down
	@docker image prune -f
	@echo "✅ Cleanup completed"

clean-all:
	@echo "🧹 WARNING: This will delete ALL data including uploads and logs!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@docker-compose down -v
	@docker system prune -a -f
	@echo "✅ Complete cleanup completed"

# Development targets
test:
	@echo "🧪 Running API tests..."
	@docker-compose exec telegram-audio-bot python test_api.py

test-local:
	@echo "🧪 Running local API tests..."
	@python test_api.py

bot-local:
	@echo "🤖 Starting bot locally..."
	@python bot_main.py

shell:
	@echo "🐚 Opening shell in container..."
	@docker-compose exec telegram-audio-bot /bin/bash

sync-config:
	@echo "🔄 Syncing whitelist_config.py from Docker volume..."
	@python scripts/sync_whitelist_config.py || bash scripts/sync_whitelist_config.sh || echo "⚠️  Sync failed - check if container/volume exists"
