#!/bin/bash
# Initial setup script for production deployment

set -e

echo "🔧 Setting up Telegram Audio Bot for production..."

# Make all scripts executable
echo "📝 Making scripts executable..."
chmod +x scripts/*.sh

# Check if .env exists
if [[ ! -f ".env" ]]; then
    echo "📋 Creating .env file from template..."
    if [[ -f "env.production.example" ]]; then
        cp env.production.example .env
        echo "✅ Created .env file from template"
        echo "⚠️  Please edit .env with your actual API keys before deploying"
    else
        echo "❌ Template file env.production.example not found"
        exit 1
    fi
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p uploads logs tmp
echo "✅ Directories created"

# Check Docker installation
echo "🐳 Checking Docker installation..."
if command -v docker >/dev/null 2>&1; then
    echo "✅ Docker is installed: $(docker --version)"
else
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if command -v docker-compose >/dev/null 2>&1; then
    echo "✅ Docker Compose is installed: $(docker-compose --version)"
else
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Test configuration (without starting services)
echo "🧪 Testing Docker configuration..."
if docker-compose config >/dev/null 2>&1; then
    echo "✅ Docker Compose configuration is valid"
else
    echo "❌ Docker Compose configuration has errors"
    docker-compose config
    exit 1
fi

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env with your actual API keys"
echo "2. Run: ./scripts/deploy.sh"
echo "3. Monitor: ./scripts/monitor.sh"
echo ""
echo "📖 For detailed instructions, see PRODUCTION.md"
