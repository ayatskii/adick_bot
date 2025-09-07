#!/usr/bin/env python3
"""
Debug script to investigate the empty response issue in production
"""
import asyncio
import logging
import os
from app.services.gemini_client import GeminiClient

# Configure logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_empty_response():
    """Debug the empty response issue"""
    
    logger.info("🔍 Debugging Gemini API Empty Response Issue")
    logger.info("=" * 60)
    
    try:
        # Check API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found")
            return
        
        # Initialize client
        client = GeminiClient()
        logger.info("✅ Client initialized")
        
        # Test with the exact text that caused the issue
        test_text = "Hello. My name is Asya. I am 33 years old. Uh, the first thing I want to say about myself is that I am a mom."
        
        logger.info(f"🧪 Testing with problematic text: '{test_text[:50]}...'")
        
        # Try structured output
        result = await client.check_grammar_structured(test_text, context="transcribed_speech")
        
        if result.get("success"):
            logger.info("✅ Structured output worked!")
            logger.info(f"Corrected: {result.get('corrected_text', 'N/A')}")
            logger.info(f"Issues: {len(result.get('grammar_issues', []))}")
            logger.info(f"Tips: {len(result.get('speaking_tips', []))}")
        else:
            logger.error(f"❌ Structured output failed: {result.get('error')}")
            
            # Try legacy fallback
            logger.info("🔄 Testing legacy fallback...")
            legacy_result = await client.check_grammar(test_text, context="transcribed_speech")
            
            if legacy_result.get("success"):
                logger.info("✅ Legacy parsing worked!")
                logger.info(f"Corrected: {legacy_result.get('corrected_text', 'N/A')}")
            else:
                logger.error(f"❌ Legacy also failed: {legacy_result.get('error')}")
        
        # Test API health
        logger.info("🏥 Testing API health...")
        health = await client.check_api_health()
        logger.info(f"Health check: {health}")
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(debug_empty_response())
