# Telegram Audio Bot Usage Guide

## 🎯 Overview

The Telegram Audio Bot is a sophisticated AI-powered bot that processes audio messages, transcribes speech using ElevenLabs API, and checks/corrects grammar using OpenAI GPT.

## 🚀 Quick Start

### 1. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.production.example .env
# Edit .env with your API keys

# Run the bot locally
python bot_main.py
# or
make bot-local
```

### 2. Production Deployment
```bash
# Initial setup
make setup

# Deploy to production
make deploy

# Monitor the bot
make monitor
```

## 🎤 Bot Features

### Commands
- `/start` - Welcome message and bot introduction
- `/help` - Comprehensive help and usage instructions
- `/status` - Bot and service health status
- `/stats` - User's personal usage statistics

### Audio Processing
The bot processes these audio types:
- **Voice Messages** - Direct voice recordings from Telegram
- **Audio Files** - MP3, WAV, M4A, AAC, OGG files
- **Video Notes** - Round video messages (audio extracted)
- **Audio Documents** - Audio files sent as documents

### Processing Pipeline
1. **Audio Download** - Securely downloads audio from Telegram
2. **Validation** - Checks file size, format, and integrity  
3. **Transcription** - Uses ElevenLabs Scribe API for speech-to-text
4. **Grammar Check** - Uses OpenAI for grammar correction
5. **Response** - Returns both original and corrected transcriptions

## 🌍 Language Support

- **99+ Languages** supported with auto-detection
- **High Accuracy** transcription for major languages
- **Context-Aware** grammar correction
- **Multi-Speaker** detection (when available)

## 📊 User Experience

### Successful Processing
```
✅ Voice message processed successfully!

🎤 Original Transcription:
This are a test message with some grammar errors.

📝 Grammar Corrected:
This is a test message with some grammar errors.

📊 Processing Details:
• Language: English
• Processing Time: 12.3s
• Confidence: 94.2%
• File Size: 1.2MB
```

### Error Handling
The bot provides clear error messages for:
- File size too large (>25MB)
- Unsupported audio formats
- Network connectivity issues
- API service errors
- Corrupted audio files

## 🛠️ Configuration

### Environment Variables
```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
ELEVENLABS_API_KEY=your_elevenlabs_api_key
OPENAI_API_KEY=your_openai_api_key

# Optional
ELEVEN_LABS_MODEL=eleven_multilingual_v2
OPENAI_MODEL=gpt-4o-mini
MAX_FILE_SIZE=26214400  # 25MB
LOG_LEVEL=INFO
POLLING_INTERVAL=1.0
```

### API Key Setup

#### 1. Telegram Bot Token
1. Message @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the token to `TELEGRAM_BOT_TOKEN`

#### 2. ElevenLabs API Key
1. Sign up at [ElevenLabs](https://elevenlabs.io)
2. Go to Profile → API Keys
3. Generate a new key with transcription permissions
4. Copy to `ELEVENLABS_API_KEY`

#### 3. OpenAI API Key
1. Visit [OpenAI Platform](https://platform.openai.com)
2. Create a new API key
3. Copy to `OPENAI_API_KEY`

## 🔧 Development

### Running Tests
```bash
# Test API connectivity
make test-local

# Test in Docker
make test
```

### Local Development
```bash
# Run bot locally with hot reload
python bot_main.py

# Monitor logs
tail -f logs/bot.log
```

### Docker Development
```bash
# Build and run in Docker
make build
make start

# View logs
make logs

# Check health
make health
```

## 📈 Monitoring

### Health Checks
The bot provides comprehensive health monitoring:
- ElevenLabs API connectivity
- OpenAI API connectivity
- File system access
- Memory and CPU usage

### Logging
- **Development**: Human-readable console logs
- **Production**: Structured JSON logs for aggregation
- **File Rotation**: Automatic log rotation (10MB max, 5 files)

### Statistics
- User session tracking
- Processing time metrics
- Success/failure rates
- File size analytics

## 🔒 Security

### Production Security
- Non-root container execution
- Read-only filesystem
- Resource limits (CPU/Memory)
- No privilege escalation
- Secure file handling with cleanup

### Data Privacy
- Temporary files automatically deleted
- No audio content stored permanently
- User data limited to session statistics
- All processing is stateless

## 🚨 Troubleshooting

### Common Issues

#### Bot Not Responding
```bash
# Check bot status
make health

# View recent logs
make logs

# Restart bot
make restart
```

#### Audio Processing Failed
- Check file size (<25MB)
- Ensure clear audio quality
- Verify API keys are valid
- Check service status with `/status`

#### Service Health Issues
```bash
# Check API connectivity
python test_api.py

# Verify environment variables
printenv | grep -E "(TELEGRAM|ELEVEN|OPENAI)"
```

### Support

For issues:
1. Check `/status` command in bot
2. Review logs: `make logs`
3. Test APIs: `make test-local`
4. Check configuration: Review `.env` file
5. Restart services: `make restart`

## 📝 Usage Examples

### Basic Voice Message
1. Start bot with `/start`
2. Send a voice message
3. Receive transcription + grammar correction

### Audio File Processing
1. Send an MP3/WAV file
2. Bot processes and transcribes
3. Get detailed results with metadata

### Multi-Language Support
1. Send audio in any supported language
2. Bot auto-detects language
3. Receives transcription in original language

## 🎯 Best Practices

### For Users
- Speak clearly and at moderate pace
- Minimize background noise
- Use supported audio formats
- Keep files under 25MB

### For Developers
- Monitor API quotas and limits
- Implement proper error handling
- Use structured logging
- Set up health monitoring
- Regular security updates

This bot provides professional-grade audio processing with enterprise-level reliability and security.
