#!/usr/bin/env python3
"""
API Health Check Script for Telegram Audio Bot

This script tests the health of all external APIs used by the bot:
- ElevenLabs Speech-to-Text API
- Google Gemini API
- Basic configuration validation

Usage:
    python test_api.py
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.services.elevenlabs_client import ElevenLabsClient
from app.services.gemini_client import GeminiClient
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_configuration():
    """Test basic configuration settings"""
    print("🔧 Testing Configuration...")
    
    try:
        # Test required fields
        assert settings.telegram_bot_token, "TELEGRAM_BOT_TOKEN is required"
        assert settings.elevenlabs_api_key, "ELEVENLABS_API_KEY is required"
        assert settings.gemini_api_key, "GEMINI_API_KEY is required"
        
        print(f"✅ Telegram Bot Token: {'*' * 10}...{settings.telegram_bot_token[-4:]}")
        print(f"✅ ElevenLabs API Key: {'*' * 10}...{settings.elevenlabs_api_key[-4:]}")
        print(f"✅ Gemini API Key: {'*' * 10}...{settings.gemini_api_key[-4:]}")
        print(f"✅ ElevenLabs Model: {settings.elevenlabs_model}")
        print(f"✅ Gemini Model: {settings.gemini_model}")
        print(f"✅ Upload Directory: {settings.upload_dir}")
        print(f"✅ Max File Size: {settings.max_file_size / 1024 / 1024:.1f}MB")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        return False

async def test_elevenlabs_api():
    """Test ElevenLabs API connectivity"""
    print("\n🎤 Testing ElevenLabs API...")
    
    try:
        client = ElevenLabsClient()
        health = await client.check_api_health()
        
        if health.get("healthy", False):
            print("✅ ElevenLabs API is healthy")
            print(f"   - Model: {health.get('model', 'Unknown')}")
            print(f"   - API Accessible: {health.get('api_accessible', False)}")
            return True
        else:
            print(f"❌ ElevenLabs API unhealthy: {health.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ ElevenLabs API Error: {e}")
        return False

async def test_gemini_api():
    """Test Google Gemini API connectivity"""
    print("\n🧠 Testing Google Gemini API...")
    
    try:
        client = GeminiClient()
        health = await client.check_api_health()
        
        if health.get("healthy", False):
            print("✅ Gemini API is healthy")
            print(f"   - Model: {health.get('model', 'Unknown')}")
            print(f"   - API Accessible: {health.get('api_accessible', False)}")
            test_response = health.get('test_response', '')
            if test_response and len(test_response) > 50:
                test_response = test_response[:50] + "..."
            print(f"   - Test Response: {test_response}")
            return True
        else:
            print(f"❌ Gemini API unhealthy: {health.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Telegram Audio Bot - API Health Check")
    print("=" * 50)
    
    # Track test results
    results = []
    
    # Test configuration
    results.append(await test_configuration())
    
    # Test external APIs
    results.append(await test_elevenlabs_api())
    results.append(await test_gemini_api())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All {total} tests passed!")
        print("🎉 Bot is ready for production!")
        sys.exit(0)
    else:
        print(f"❌ {total - passed} out of {total} tests failed")
        print("🔧 Please fix the issues above before deploying")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        logger.error("Test failed with unexpected error", exc_info=True)
        sys.exit(1)
