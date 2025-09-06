# Production Deployment Guide

This document provides comprehensive instructions for deploying the Telegram Audio Bot to production using Docker.

## 🚀 Quick Start

1. **Set up environment variables:**
   ```bash
   cp env.production.example .env
   # Edit .env with your actual API keys
   ```

2. **Make scripts executable:**
   ```bash
   chmod +x scripts/*.sh
   ```

3. **Deploy to production:**
   ```bash
   ./scripts/deploy.sh
   ```

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- Bash shell
- Valid API keys for:
  - Telegram Bot (from @BotFather)
  - ElevenLabs API
  - Google Gemini API

## 🔧 Configuration

### Environment Variables

Copy `env.production.example` to `.env` and configure:

```env
# Required API Keys
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ELEVENLABS_API_KEY=your_elevenlabs_api_key
GEMINI_API_KEY=your_gemini_api_key

# Model Configuration
ELEVEN_LABS_MODEL=eleven_multilingual_v2
GEMINI_MODEL=gemini-2.5-pro

# Application Settings
MAX_FILE_SIZE=26214400  # 25MB
UPLOAD_DIR=uploads
LOG_LEVEL=INFO
POLLING_INTERVAL=1.0
```

## 🏗️ Production Scripts

### Build Script
```bash
./scripts/build.sh
```
- Builds optimized production Docker image
- Uses multi-stage build for minimal size
- Shows image size and layer information

### Deploy Script
```bash
./scripts/deploy.sh
```
- Validates environment variables
- Stops existing containers gracefully
- Builds and starts production service
- Waits for service readiness
- Shows deployment status

### Health Check Script
```bash
./scripts/health-check.sh
```
- Checks container health status
- Shows resource usage
- Displays recent application logs
- Validates service availability

### Monitor Script
```bash
./scripts/monitor.sh
```
- Shows comprehensive monitoring dashboard
- Container status and resource usage
- Volume usage statistics
- Recent logs and health status

## 🐳 Docker Configuration

### Multi-Stage Dockerfile

The production Dockerfile uses a multi-stage build:

1. **Dependencies Stage**: Installs build tools and Python packages
2. **Runtime Stage**: Minimal production image with only runtime dependencies

### Security Features

- ✅ Non-root user execution
- ✅ Read-only filesystem
- ✅ No privilege escalation
- ✅ Resource limits (CPU/Memory)
- ✅ Health monitoring
- ✅ Proper signal handling

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '1.0'
      memory: 1G
```

## 📊 Monitoring & Operations

### View Real-time Logs
```bash
docker-compose logs -f telegram-audio-bot
```

### Check Container Status
```bash
docker-compose ps
```

### Monitor Resource Usage
```bash
docker stats telegram-audio-bot
```

### Update Application
```bash
docker-compose down
docker-compose up -d --build
```

## 💾 Data Management

### Persistent Volumes

- `audio_uploads`: Stores uploaded audio files
- `app_logs`: Application logs

### Backup Data
```bash
# Backup uploads
docker run --rm -v telegram-audio-bot_audio_uploads:/data \
  -v $(pwd):/backup busybox \
  tar czf /backup/uploads-backup.tar.gz -C /data .

# Backup logs
docker run --rm -v telegram-audio-bot_app_logs:/data \
  -v $(pwd):/backup busybox \
  tar czf /backup/logs-backup.tar.gz -C /data .
```

### Restore Data
```bash
# Restore uploads
docker run --rm -v telegram-audio-bot_audio_uploads:/data \
  -v $(pwd):/backup busybox \
  tar xzf /backup/uploads-backup.tar.gz -C /data

# Restore logs  
docker run --rm -v telegram-audio-bot_app_logs:/data \
  -v $(pwd):/backup busybox \
  tar xzf /backup/logs-backup.tar.gz -C /data
```

## 🔧 Troubleshooting

### Container Won't Start
```bash
# Check container logs
docker-compose logs telegram-audio-bot

# Check system resources
docker system df

# Rebuild with no cache
docker-compose build --no-cache
```

### High Memory Usage
```bash
# Check resource usage
./scripts/monitor.sh

# Restart container
docker-compose restart telegram-audio-bot
```

### Bot Not Responding
```bash
# Check health status
./scripts/health-check.sh

# Validate API keys
docker-compose exec telegram-audio-bot python test_api.py
```

## 🧹 Cleanup

### Remove Application
```bash
# Stop and remove containers
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker image prune -f
```

### Complete Cleanup
```bash
# Remove everything (USE WITH CAUTION)
docker-compose down -v
docker system prune -a -f
```

## 🚦 Production Checklist

### Before Deployment
- [ ] API keys configured in `.env`
- [ ] Scripts made executable (`chmod +x scripts/*.sh`)
- [ ] Server resources adequate (2GB+ RAM, 10GB+ disk)
- [ ] Docker and Docker Compose installed
- [ ] Firewall configured if needed

### After Deployment
- [ ] Container running (`docker-compose ps`)
- [ ] Health check passing (`./scripts/health-check.sh`)
- [ ] Bot responding to test messages
- [ ] Monitoring setup (`./scripts/monitor.sh`)
- [ ] Backup strategy implemented
- [ ] Log rotation configured

## 📞 Support

For issues or questions:
1. Check container logs: `docker-compose logs telegram-audio-bot`
2. Run health check: `./scripts/health-check.sh`
3. Monitor resources: `./scripts/monitor.sh`
4. Review this documentation

## 🔄 Updates

To update the application:
1. Pull latest code: `git pull`
2. Rebuild: `./scripts/build.sh`
3. Deploy: `./scripts/deploy.sh`
4. Verify: `./scripts/health-check.sh`
