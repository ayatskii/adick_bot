#!/usr/bin/env python3
"""
Test script for the improved Gemini API structured output implementation
"""
import asyncio
import json
import logging
from typing import Dict, Any

# Import our updated client
from app.services.gemini_client import GeminiClient, GrammarAnalysisResponse
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_structured_output():
    """Test the new structured output implementation"""
    
    logger.info("🧪 Testing Gemini API Structured Output Implementation")
    logger.info("=" * 60)
    
    # Initialize client
    try:
        client = GeminiClient()
        logger.info("✅ Gemini client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize client: {e}")
        return
    
    # Test cases
    test_cases = [
        {
            "name": "Simple Grammar Error",
            "text": "I goes to the store yesterday and buyed some apples.",
            "expected_corrections": True
        },
        {
            "name": "Perfect Grammar",
            "text": "I went to the store yesterday and bought some apples.",
            "expected_corrections": False
        },
        {
            "name": "Complex Sentence",
            "text": "The report which was written by me and my colleague are very comprehensive and covers all aspects of the project.",
            "expected_corrections": True
        },
        {
            "name": "Technical Text",
            "text": "The API endpoint returns a JSON response that contains the users data and authentication token.",
            "expected_corrections": True
        }
    ]
    
    logger.info(f"\n📋 Running {len(test_cases)} test cases...\n")
    
    # Test API health first
    logger.info("🏥 Testing API health...")
    health = await client.check_api_health()
    logger.info(f"API Health: {health}")
    
    if not health.get("healthy"):
        logger.error("❌ API is not healthy, skipping tests")
        return
    
    if not health.get("structured_output_support"):
        logger.warning("⚠️ Structured output may not be supported, proceeding with caution")
    
    # Run test cases
    results = []
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n📝 Test {i}: {test_case['name']}")
        logger.info(f"Input: '{test_case['text']}'")
        
        try:
            # Test structured approach
            result = await client.check_grammar_structured(
                text=test_case['text'],
                context="test_case"
            )
            
            if result.get("success"):
                logger.info("✅ Structured parsing successful")
                logger.info(f"Corrected: '{result.get('corrected_text', 'N/A')}'")
                logger.info(f"Confidence: {result.get('confidence_score', 0):.2f}")
                logger.info(f"Improvements: {result.get('improvements_made', 0)}")
                logger.info(f"Grammar Issues: {len(result.get('grammar_issues', []))}")
                logger.info(f"Speaking Tips: {len(result.get('speaking_tips', []))}")
                
                # Log first few issues and tips for verification
                issues = result.get('grammar_issues', [])
                if issues:
                    logger.info(f"First issue: {issues[0][:100]}...")
                
                tips = result.get('speaking_tips', [])
                if tips:
                    logger.info(f"First tip: {tips[0][:100]}...")
                    
            else:
                logger.error(f"❌ Structured parsing failed: {result.get('error')}")
            
            results.append({
                "test_case": test_case['name'],
                "success": result.get("success"),
                "method": "structured",
                "processing_time": result.get("processing_time", 0),
                "improvements": result.get("improvements_made", 0),
                "error": result.get("error")
            })
            
        except Exception as e:
            logger.error(f"❌ Test failed with exception: {e}")
            results.append({
                "test_case": test_case['name'],
                "success": False,
                "method": "structured",
                "error": str(e)
            })
    
    # Test retry mechanism
    logger.info(f"\n🔄 Testing retry mechanism...")
    try:
        retry_result = await client.check_grammar_with_retry(
            text="This are a test of the retry mechanism.",
            context="retry_test",
            max_retries=2,
            use_structured=True
        )
        
        if retry_result.get("success"):
            logger.info("✅ Retry mechanism works")
            logger.info(f"Method used: {retry_result.get('method_used', 'unknown')}")
            logger.info(f"Retry attempts: {retry_result.get('retry_attempts', 0)}")
        else:
            logger.error(f"❌ Retry mechanism failed: {retry_result.get('error')}")
            
    except Exception as e:
        logger.error(f"❌ Retry test failed: {e}")
    
    # Summary
    logger.info(f"\n📊 Test Summary")
    logger.info("=" * 40)
    successful_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    logger.info(f"Successful tests: {successful_tests}/{total_tests}")
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        logger.info(f"{status} {result['test_case']}: {result.get('processing_time', 0):.2f}s")
        if result.get('error'):
            logger.info(f"   Error: {result['error']}")
    
    logger.info(f"\n🎉 Testing completed!")

def test_pydantic_schema():
    """Test Pydantic schema generation"""
    logger.info("\n🔍 Testing Pydantic Schema Generation")
    
    try:
        schema = GrammarAnalysisResponse.model_json_schema()
        logger.info("✅ Schema generated successfully")
        logger.info(f"Schema properties: {list(schema.get('properties', {}).keys())}")
        
        # Pretty print the schema for verification
        logger.info("Schema structure:")
        print(json.dumps(schema, indent=2))
        
    except Exception as e:
        logger.error(f"❌ Schema generation failed: {e}")

if __name__ == "__main__":
    """Run the test suite"""
    
    # Check configuration
    if not all([settings.gemini_api_key, settings.telegram_bot_token]):
        logger.error("❌ Missing required API keys in configuration")
        exit(1)
    
    # Test schema first
    test_pydantic_schema()
    
    # Run async tests
    try:
        asyncio.run(test_structured_output())
    except KeyboardInterrupt:
        logger.info("👋 Testing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Testing failed: {e}")
        raise
