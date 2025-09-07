"""
Google Gemini API Client for Grammar Checking and Text Improvement
Advanced implementation with intelligent prompting and response handling
"""
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Advanced Gemini API client for grammar checking and text improvement
    
    Features:
    - Context-aware grammar correction
    - Multiple correction strategies
    - Intelligent prompt engineering
    - Retry logic with backoff
    - Response validation and cleaning
    """
    
    def __init__(self):
        """Initialize Gemini client with API credentials"""
        
        # Validate API key
        if not settings.gemini_api_key or settings.gemini_api_key == "your_key_here":
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
        
        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)
        
        # Initialize model with safety settings
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        )
        
        # Generation configuration for consistent results
        self.generation_config = {
            "temperature": 0.1,  # Low temperature for consistent grammar correction
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        logger.info(f"Gemini client initialized with model: {settings.gemini_model}")
    
    def _create_grammar_prompt(self, text: str, context: Optional[str] = None) -> str:
        """
        Create an effective prompt for grammar checking
        
        Args:
            text: Text to check for grammar errors
            context: Optional context about the text (e.g., "business email", "casual conversation")
            
        Returns:
            Formatted prompt for the AI model
        """
        
        base_prompt = """You are a professional editor and grammar expert. Your task is to correct grammar, spelling, punctuation, and improve clarity while preserving the original meaning and tone.

RULES:
1. Return ONLY the corrected text, no explanations or comments
2. Preserve the original meaning and intent
3. Maintain the original tone (formal/informal)
4. Fix grammar, spelling, punctuation, and word choice errors
5. Improve clarity and flow where needed
6. If the text is already correct, return it unchanged
7. Do not add new information or change the core message

"""
        
        if context:
            base_prompt += f"CONTEXT: This text is from a {context}. Adjust the correction style accordingly.\n\n"
        
        base_prompt += f"""TEXT TO CORRECT:
"{text}"

CORRECTED TEXT:"""
        
        return base_prompt
    
    def _create_advanced_grammar_prompt(self, text: str) -> str:
        """
        Create an advanced prompt that provides both correction and explanation
        
        Args:
            text: Text to analyze and correct
            
        Returns:
            Formatted prompt for detailed grammar analysis
        """
        
        return f"""As an expert grammar checker, analyze this text and provide corrections with explanations.

Return your response in this JSON format:
{{
    "corrected_text": "The corrected version of the text",
    "changes_made": [
        {{
            "original": "original phrase",
            "corrected": "corrected phrase", 
            "reason": "explanation of the change"
        }}
    ],
    "confidence_score": 0.95,
    "text_quality": "good/fair/poor"
}}

TEXT TO ANALYZE:
"{text}"

JSON RESPONSE:"""
    
    async def check_grammar(
        self, 
        text: str, 
        context: Optional[str] = None,
        advanced_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Check and correct grammar in the provided text
        
        Args:
            text: Text to check for grammar errors
            context: Optional context for better corrections
            advanced_mode: Return detailed analysis if True
            
        Returns:
            Dictionary with correction results:
            {
                "success": bool,
                "original_text": str,
                "corrected_text": str,
                "changes_made": List[Dict] (if advanced_mode),
                "confidence_score": float (if advanced_mode),
                "processing_time": float,
                "error": str (if failed)
            }
        """
        try:
            if not text or not text.strip():
                return {"success": False, "error": "Empty text provided"}
            
            logger.info(f"Starting grammar check for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            start_time = time.time()
            
            # Choose prompt based on mode
            if advanced_mode:
                prompt = self._create_advanced_grammar_prompt(text.strip())
            else:
                prompt = self._create_grammar_prompt(text.strip(), context)
            
            # Generate response
            response = await self.model.generate_content_async(
                prompt,
                generation_config=self.generation_config
            )
            
            processing_time = time.time() - start_time
            
            if not response:
                return {"success": False, "error": "No response from Gemini API"}
            
            # Debug: Log response structure
            logger.debug(f"Response type: {type(response)}")
            logger.debug(f"Response has candidates: {hasattr(response, 'candidates')}")
            
            # More robust response extraction
            try:
                if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts and len(candidate.content.parts) > 0:
                            raw_response = candidate.content.parts[0].text.strip()
                        else:
                            # Try direct text access
                            raw_response = str(candidate.content).strip()
                    else:
                        raw_response = str(candidate).strip()
                elif hasattr(response, 'text'):
                    # Direct text response
                    raw_response = response.text.strip()
                else:
                    # Last resort - convert to string
                    raw_response = str(response).strip()
                    
                if not raw_response:
                    return {"success": False, "error": "Empty response text from Gemini API"}
                    
                # Log more details for debugging
                logger.info(f"Raw response (first 200 chars): {raw_response[:200]}...")
                
            except Exception as parse_error:
                logger.error(f"Error parsing Gemini response: {parse_error}")
                return {"success": False, "error": f"Failed to parse Gemini response: {parse_error}"}
            
            if advanced_mode:
                # Parse JSON response for advanced mode
                result = self._parse_advanced_response(raw_response, text)
            else:
                # Clean simple response
                corrected_text = self._clean_simple_response(raw_response)
                result = {
                    "success": True,
                    "original_text": text,
                    "corrected_text": corrected_text,
                    "processing_time": processing_time
                }
            
            logger.info(f"Grammar check completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Grammar check error: {e}", exc_info=True)
            return {
                "success": False, 
                "error": f"Grammar check failed: {str(e)}",
                "original_text": text
            }
    
    def _clean_simple_response(self, response_text: str) -> str:
        """
        Clean the simple grammar correction response
        
        Args:
            response_text: Raw response from the AI model
            
        Returns:
            Cleaned corrected text
        """
        # Remove common prefixes that the AI might add
        prefixes_to_remove = [
            "CORRECTED TEXT:",
            "Corrected text:",
            "corrected text:",
            "CORRECTED:",
            "Corrected:",
            "Here is the corrected text:",
            "The corrected text is:",
            "The corrected version is:",
        ]
        
        cleaned = response_text.strip()
        
        # Handle API response structure artifacts
        if 'role: "model"' in cleaned:
            # This looks like a raw API response, try to extract just the text
            lines = cleaned.split('\n')
            # Find lines that look like actual corrected text (not metadata)
            text_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('role:') and not line.startswith('{') and not line.startswith('}'):
                    text_lines.append(line)
            if text_lines:
                cleaned = ' '.join(text_lines)
        
        # Remove common prefixes that the AI might add
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        
        # Remove surrounding quotes
        if (cleaned.startswith('"') and cleaned.endswith('"')) or \
           (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        
        # Remove markdown formatting if present
        cleaned = cleaned.replace("**", "").replace("*", "")
        
        # Check if the result is just metadata or empty
        if not cleaned or cleaned.lower().startswith('role:') or len(cleaned.strip()) < 10:
            # If we got metadata or very short response, it's likely an error
            # Return a message indicating grammar check wasn't successful
            return "Grammar check unavailable - original text preserved"
        
        return cleaned
    
    def _parse_advanced_response(self, response_text: str, original_text: str) -> Dict[str, Any]:
        """
        Parse advanced JSON response from the AI model
        
        Args:
            response_text: Raw JSON response
            original_text: Original input text
            
        Returns:
            Parsed response dictionary
        """
        try:
            import json
            
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                parsed_response = json.loads(json_text)
                
                return {
                    "success": True,
                    "original_text": original_text,
                    "corrected_text": parsed_response.get("corrected_text", original_text),
                    "changes_made": parsed_response.get("changes_made", []),
                    "confidence_score": parsed_response.get("confidence_score", 0.0),
                    "text_quality": parsed_response.get("text_quality", "unknown")
                }
            else:
                # Fallback to simple cleaning
                cleaned_text = self._clean_simple_response(response_text)
                return {
                    "success": True,
                    "original_text": original_text,
                    "corrected_text": cleaned_text,
                    "changes_made": [],
                    "confidence_score": 0.8,
                    "text_quality": "processed_without_analysis"
                }
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            # Fallback to simple cleaning
            cleaned_text = self._clean_simple_response(response_text)
            return {
                "success": True,
                "original_text": original_text,
                "corrected_text": cleaned_text,
                "changes_made": [],
                "confidence_score": 0.7,
                "text_quality": "processed_with_fallback"
            }
    
    async def check_grammar_with_retry(
        self, 
        text: str, 
        context: Optional[str] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Check grammar with retry logic for better reliability
        
        Args:
            text: Text to check
            context: Optional context
            max_retries: Maximum retry attempts
            retry_delay: Initial delay between retries
            
        Returns:
            Grammar check result with retry information
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Grammar check attempt {attempt + 1}/{max_retries + 1}")
                
                result = await self.check_grammar(text, context)
                
                if result.get("success"):
                    if attempt > 0:
                        logger.info(f"Grammar check succeeded after {attempt + 1} attempts")
                    result["retry_attempts"] = attempt
                    return result
                
                last_error = result.get("error", "Unknown error")
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(f"Grammar check attempt {attempt + 1} failed: {last_error}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Grammar check attempt {attempt + 1} exception: {e}")
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        # All attempts failed - return original text as fallback
        logger.error(f"All grammar check attempts failed: {last_error}")
        return {
            "success": False,
            "error": f"Grammar check failed after {max_retries + 1} attempts: {last_error}",
            "original_text": text,
            "corrected_text": text,  # Fallback to original text
            "retry_attempts": max_retries + 1,
            "fallback_used": True
        }
    
    async def batch_check_grammar(self, texts: List[str], context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check grammar for multiple texts in batch
        
        Args:
            texts: List of texts to check
            context: Optional context for all texts
            
        Returns:
            List of grammar check results
        """
        logger.info(f"Starting batch grammar check for {len(texts)} texts")
        
        # Process texts concurrently with semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
        
        async def check_single_text(text: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.check_grammar_with_retry(text, context)
        
        results = await asyncio.gather(
            *[check_single_text(text) for text in texts],
            return_exceptions=True
        )
        
        # Handle any exceptions that occurred
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "original_text": texts[i],
                    "corrected_text": texts[i]
                })
            else:
                processed_results.append(result)
        
        logger.info(f"Batch grammar check completed: {len(processed_results)} results")
        return processed_results
    
    async def check_api_health(self) -> Dict[str, Any]:
        """
        Check Gemini API health and accessibility
        
        Returns:
            Health status dictionary
        """
        try:
            # Simple test request
            test_response = await self.model.generate_content_async(
                "Test message for API health check",
                generation_config={"max_output_tokens": 10}
            )
            
            # Extract response text safely
            response_text = "No response"
            if test_response and test_response.candidates and len(test_response.candidates) > 0:
                candidate = test_response.candidates[0]
                if candidate.content and candidate.content.parts and len(candidate.content.parts) > 0:
                    response_text = candidate.content.parts[0].text
            
            return {
                "healthy": True,
                "api_accessible": True,
                "model": settings.gemini_model,
                "test_response": response_text
            }
            
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return {
                "healthy": False,
                "api_accessible": False,
                "model": settings.gemini_model,
                "error": str(e)
            }
