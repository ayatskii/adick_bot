"""
OpenAI Client for Grammar Checking and Text Improvement
Advanced implementation with intelligent prompting and response handling using OpenAI API
"""
import logging
import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from openai import AsyncOpenAI
from openai import OpenAIError, APIError, RateLimitError, APIConnectionError

from app.config import settings

logger = logging.getLogger(__name__)

class GrammarIssue(BaseModel):
    """Model for individual grammar issues"""
    issue: str = Field(description="Brief description of the grammar issue")
    explanation: str = Field(description="Detailed explanation of why this is an issue and how to fix it")

class GrammarAnalysisResponse(BaseModel):
    """Structured response model for grammar analysis"""
    corrected_text: str = Field(description="The grammatically corrected version of the input text")
    grammar_issues: List[GrammarIssue] = Field(
        default=[],
        description="List of grammar, spelling, and punctuation issues found in the original text"
    )
    speaking_tips: List[str] = Field(
        default=[],
        description="List of specific suggestions for improving speaking and communication skills"
    )
    confidence_score: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence level of the grammar corrections (0.0 to 1.0)"
    )
    improvements_made: int = Field(
        default=0,
        ge=0,
        description="Number of grammar improvements made to the original text"
    )

class OpenAIClient:
    """
    Advanced OpenAI client for grammar checking and text improvement
    
    Features:
    - Context-aware grammar correction
    - Multiple correction strategies
    - Intelligent prompt engineering
    - Retry logic with backoff
    - Response validation and cleaning
    """
    
    def __init__(self):
        """Initialize OpenAI client with API key"""
        
        # Validate API key
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        # Initialize OpenAI client
        try:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            logger.info(f"OpenAI client initialized with model: {settings.openai_model}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise ValueError(f"OpenAI initialization failed: {e}")
        
        # Model configuration
        self.model = settings.openai_model
        self.temperature = 0.1  # Low temperature for consistent grammar correction
        self.max_tokens = 4096
        
        logger.info(f"OpenAI client initialized successfully")
    
    def _create_grammar_schema(self) -> Dict[str, Any]:
        """
        Create a JSON schema for structured output
        
        Returns:
            Schema dictionary for grammar analysis response
        """
        return {
            "type": "object",
            "properties": {
                "corrected_text": {
                    "type": "string",
                    "description": "The grammatically corrected version of the input text"
                },
                "grammar_issues": {
                    "type": "array",
                    "description": "List of grammar, spelling, and punctuation issues found",
                    "items": {
                        "type": "object",
                        "properties": {
                            "issue": {
                                "type": "string",
                                "description": "Brief description of the grammar issue"
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Detailed explanation of why this is an issue and how to fix it"
                            }
                        },
                        "required": ["issue", "explanation"]
                    }
                },
                "speaking_tips": {
                    "type": "array",
                    "description": "List of specific suggestions for improving speaking and communication skills",
                    "items": {
                        "type": "string"
                    }
                },
                "confidence_score": {
                    "type": "number",
                    "description": "Confidence level of the grammar corrections (0.0 to 1.0)"
                },
                "improvements_made": {
                    "type": "integer",
                    "description": "Number of grammar improvements made to the original text"
                }
            },
            "required": ["corrected_text", "grammar_issues", "speaking_tips", "confidence_score", "improvements_made"]
        }
    
    def _create_structured_grammar_prompt(self, text: str, context: Optional[str] = None) -> str:
        """
        Create an optimized prompt for structured grammar checking
        
        Args:
            text: Text to check for grammar errors
            context: Optional context about the text (e.g., "business email", "casual conversation")
            
        Returns:
            Formatted prompt for the AI model optimized for structured output
        """
        
        schema = self._create_grammar_schema()
        
        base_prompt = f"""You are a professional editor and grammar expert. Analyze the provided text and return a comprehensive grammar analysis.

Your task is to:
1. Correct all grammar, spelling, punctuation, and clarity issues while preserving the original meaning and tone
2. Identify specific grammar mistakes with detailed explanations
3. Provide practical speaking improvement suggestions
4. Assess the quality of your corrections with a confidence score

RULES:
- Preserve the original meaning and intent completely
- Maintain the original tone (formal/informal) 
- Fix grammar, spelling, punctuation, and word choice errors
- Improve clarity and flow where appropriate
- If the text is already perfect, acknowledge this but still provide general speaking tips
- Do not add new information or change the core message
- Count the actual number of improvements made

"""
        
        if context:
            base_prompt += f"CONTEXT: This text is from a {context}. Adjust the correction style accordingly.\n\n"
        
        base_prompt += f"""TEXT TO ANALYZE:
"{text}"

You MUST respond with valid JSON matching this exact schema:
{json.dumps(schema, indent=2)}

Respond ONLY with the JSON object, no additional text."""
        
        return base_prompt
    
    def _create_grammar_prompt(self, text: str, context: Optional[str] = None) -> str:
        """
        Create an effective prompt for grammar checking
        
        Args:
            text: Text to check for grammar errors
            context: Optional context about the text (e.g., "business email", "casual conversation")
            
        Returns:
            Formatted prompt for the AI model
        """
        
        base_prompt = """You are a professional editor and grammar expert. Your task is to correct grammar, spelling, punctuation, and improve clarity while preserving the original meaning and tone. Additionally, you will provide feedback on grammar mistakes and speaking improvement suggestions.

RULES:
1. First, provide the corrected text in a clear, formatted section
2. Then explain any grammar, spelling, or punctuation mistakes you found
3. Offer specific suggestions for improving speaking and communication skills
4. Preserve the original meaning and intent in your corrections
5. Maintain the original tone (formal/informal)
6. Fix grammar, spelling, punctuation, and word choice errors
7. Improve clarity and flow where needed
8. If the text is already correct, acknowledge this and still provide general speaking tips
9. Do not add new information or change the core message
10. Format your response as JSON with clear sections: "corrected_text," "grammar_issues," and "speaking_tips"

You MUST respond with valid JSON in this exact format:
{
  "corrected_text": "The grammatically corrected version of the text",
  "grammar_issues": [
    {
      "issue": "Issue title",
      "explanation": "Detailed explanation of the grammar issue"
    }
  ],
  "speaking_tips": ["List of specific suggestions for improving speaking and communication"]
}

"""
        
        if context:
            base_prompt += f"CONTEXT: This text is from a {context}. Adjust the correction style accordingly.\n\n"
        
        base_prompt += f"""TEXT TO CORRECT:
"{text}"

Respond ONLY with the JSON object, no additional text."""
        
        return base_prompt
    
    async def check_grammar_structured(
        self, 
        text: str, 
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check and correct grammar using structured output from OpenAI
        
        Args:
            text: Text to check for grammar errors
            context: Optional context for better corrections
            
        Returns:
            Dictionary with correction results using structured parsing
        """
        try:
            if not text or not text.strip():
                return {"success": False, "error": "Empty text provided"}
            
            logger.info(f"Starting structured grammar check for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            start_time = time.time()
            
            # Create optimized prompt for structured output
            prompt = self._create_structured_grammar_prompt(text.strip(), context)
            
            # Generate response with structured output
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional grammar expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            processing_time = time.time() - start_time
            
            if not response or not response.choices:
                return {"success": False, "error": "No response from OpenAI"}
            
            # Extract and parse structured response
            try:
                raw_response = response.choices[0].message.content.strip()
                
                logger.debug(f"Raw response preview: {raw_response[:100]}...")
                
                if not raw_response:
                    logger.error("Empty response from OpenAI")
                    return {"success": False, "error": "Empty response from OpenAI"}
                
                # Parse the structured JSON response
                try:
                    parsed_response = json.loads(raw_response)
                    
                    # Validate with Pydantic model
                    try:
                        analysis = GrammarAnalysisResponse(**parsed_response)
                    except Exception as validation_error:
                        logger.warning(f"Pydantic validation failed: {validation_error}, using raw parsed data")
                    
                    # Convert to output format
                    grammar_issues_formatted = []
                    if isinstance(parsed_response.get("grammar_issues"), list):
                        for issue in parsed_response["grammar_issues"]:
                            if isinstance(issue, dict):
                                issue_text = issue.get("issue", "")
                                explanation = issue.get("explanation", "")
                                if issue_text and explanation:
                                    grammar_issues_formatted.append(f"{issue_text}: {explanation}")
                                elif issue_text:
                                    grammar_issues_formatted.append(issue_text)
                            else:
                                grammar_issues_formatted.append(str(issue))
                    
                    result = {
                        "success": True,
                        "original_text": text,
                        "corrected_text": parsed_response.get("corrected_text", text),
                        "grammar_issues": grammar_issues_formatted,
                        "speaking_tips": parsed_response.get("speaking_tips", []),
                        "confidence_score": parsed_response.get("confidence_score", 0.95),
                        "improvements_made": parsed_response.get("improvements_made", 0),
                        "processing_time": processing_time
                    }
                    
                    logger.info(f"Structured grammar check completed in {processing_time:.2f}s with {parsed_response.get('improvements_made', 0)} improvements")
                    return result
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse structured JSON response: {e}")
                    return self._fallback_to_legacy_parsing(text, raw_response, processing_time)
                    
            except Exception as parse_error:
                logger.error(f"Error parsing OpenAI response: {parse_error}")
                return {"success": False, "error": f"Failed to parse OpenAI response: {parse_error}"}
            
        except Exception as e:
            logger.error(f"Structured grammar check error: {e}", exc_info=True)
            return {
                "success": False, 
                "error": f"Grammar check failed: {str(e)}",
                "original_text": text
            }
    
    def _fallback_to_legacy_parsing(self, text: str, raw_response: str, processing_time: float) -> Dict[str, Any]:
        """
        Fallback to legacy JSON parsing when structured output fails
        
        Args:
            text: Original text
            raw_response: Raw response from API
            processing_time: Time taken for processing
            
        Returns:
            Parsed response using legacy method
        """
        logger.info("Falling back to legacy JSON parsing method")
        return self._parse_json_response(raw_response, text, processing_time)
    
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
            Dictionary with correction results
        """
        try:
            if not text or not text.strip():
                return {"success": False, "error": "Empty text provided"}
            
            logger.info(f"Starting grammar check for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            start_time = time.time()
            
            # Create prompt
            prompt = self._create_grammar_prompt(text.strip(), context)
            
            # Generate response using OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional grammar expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            processing_time = time.time() - start_time
            
            if not response or not response.choices:
                return {"success": False, "error": "No response from OpenAI"}
            
            # Extract response text
            try:
                raw_response = response.choices[0].message.content.strip()
                    
                if not raw_response:
                    return {"success": False, "error": "Empty response text from OpenAI"}
                
                logger.info(f"Raw response (first 200 chars): {raw_response[:200]}...")
                
            except Exception as parse_error:
                logger.error(f"Error parsing OpenAI response: {parse_error}")
                return {"success": False, "error": f"Failed to parse OpenAI response: {parse_error}"}
            
            # Parse JSON response
            result = self._parse_json_response(raw_response, text, processing_time)
            
            logger.info(f"Grammar check completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Grammar check error: {e}", exc_info=True)
            return {
                "success": False, 
                "error": f"Grammar check failed: {str(e)}",
                "original_text": text
            }
    
    def _parse_json_response(self, response_text: str, original_text: str, processing_time: float) -> Dict[str, Any]:
        """
        Parse JSON response from the AI model
        
        Args:
            response_text: Raw JSON response from the model
            original_text: Original input text
            processing_time: Time taken for processing
            
        Returns:
            Parsed response dictionary
        """
        try:
            import json
            import re
            
            # Clean up the response text to extract JSON
            cleaned_response = response_text.strip()
            
            # Remove any markdown code block formatting
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            # Find JSON object in the response
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = cleaned_response
            
            # Parse JSON
            parsed = json.loads(json_str)
            
            # Extract required fields - handle different field name variations
            corrected_text = (parsed.get("corrected_text") or 
                            parsed.get("correctedtext") or 
                            parsed.get("corrected") or "")
            
            # Debug logging
            logger.debug(f"Parsed JSON successfully. Corrected text: {corrected_text[:100] if corrected_text else 'None'}...")
            
            # If we didn't get corrected text, something is wrong with the JSON structure
            if not corrected_text:
                logger.warning(f"No corrected text found in parsed JSON. Keys available: {list(parsed.keys())}")
                corrected_text = original_text
            
            grammar_issues = (parsed.get("grammar_issues") or 
                            parsed.get("grammarissues") or 
                            parsed.get("issues") or [])
            
            speaking_tips = (parsed.get("speaking_tips") or 
                           parsed.get("speakingtips") or 
                           parsed.get("tips") or [])
            
            # Format grammar issues as strings
            grammar_issues_formatted = []
            if isinstance(grammar_issues, list):
                for issue in grammar_issues:
                    if isinstance(issue, dict):
                        issue_text = issue.get("issue", "")
                        explanation = issue.get("explanation", "")
                        if issue_text and explanation:
                            grammar_issues_formatted.append(f"{issue_text}: {explanation}")
                        elif issue_text:
                            grammar_issues_formatted.append(issue_text)
                    else:
                        grammar_issues_formatted.append(str(issue))
            
            # Determine number of changes
            try:
                if original_text.strip() != corrected_text.strip():
                    # Simple word diff count
                    orig_words = original_text.strip().split()
                    corr_words = corrected_text.strip().split()
                    changes = abs(len(orig_words) - len(corr_words))
                    # Add differences in matching words
                    for i in range(min(len(orig_words), len(corr_words))):
                        if orig_words[i] != corr_words[i]:
                            changes += 1
                else:
                    changes = 0
            except:
                changes = 0
            
            return {
                "success": True,
                "original_text": original_text,
                "corrected_text": corrected_text,
                "grammar_issues": grammar_issues_formatted,
                "speaking_tips": speaking_tips if isinstance(speaking_tips, list) else [],
                "processing_time": processing_time,
                "improvements_made": changes,
                "confidence_score": 0.90  # Default confidence
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}. Using original text as fallback.")
            
            return {
                "success": True,
                "original_text": original_text,
                "corrected_text": original_text,
                "grammar_issues": ["Unable to analyze grammar issues due to response format"],
                "speaking_tips": ["Try speaking more clearly and at a moderate pace"],
                "processing_time": processing_time,
                "improvements_made": 0,
                "confidence_score": 0.70  # Lower confidence for fallback
            }
        except Exception as e:
            logger.error(f"Error parsing JSON response: {e}")
            return {
                "success": False,
                "error": f"Failed to parse response: {str(e)}",
                "original_text": original_text
            }
    
    async def check_grammar_with_retry(
        self,
        text: str,
        context: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Check grammar with intelligent retry logic and exponential backoff
        
        Args:
            text: Text to check for grammar errors
            context: Optional context for better corrections
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (seconds)
            
        Returns:
            Grammar check result with retry information
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Grammar check attempt {attempt + 1}/{max_retries + 1}")
                
                result = await self.check_grammar_structured(text, context)
                
                if result.get("success"):
                    if attempt > 0:
                        logger.info(f"Grammar check succeeded after {attempt + 1} attempts")
                    result["retry_attempts"] = attempt
                    return result
                
                last_error = result.get("error", "Unknown error")
                
                # Don't retry certain types of errors
                non_retryable_errors = [
                    "Invalid API key",
                    "Empty text provided",
                    "authentication"
                ]
                
                if any(err.lower() in last_error.lower() for err in non_retryable_errors):
                    logger.error(f"Non-retryable error: {last_error}")
                    break
                
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    delay = retry_delay * (2 ** attempt) + (time.time() % 1)
                    logger.warning(f"Attempt {attempt + 1} failed: {last_error}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                
            except (RateLimitError, APIConnectionError) as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt + 1} API error: {e}")
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt + 1} exception: {e}")
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        # All attempts failed
        logger.error(f"All grammar check attempts failed. Last error: {last_error}")
        return {
            "success": False,
            "error": f"Grammar check failed after {max_retries + 1} attempts: {last_error}",
            "retry_attempts": max_retries + 1,
            "original_text": text
        }
    
    async def check_api_health(self) -> Dict[str, Any]:
        """
        Check if the OpenAI API is accessible and healthy
        
        Returns:
            Dictionary with health status
        """
        try:
            # Try a simple generation request
            test_text = "Hello world"
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": f"Say 'OK' if you can read this: {test_text}"}
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            if response and response.choices:
                return {
                    "healthy": True,
                    "message": "OpenAI API is accessible",
                    "model": self.model
                }
            else:
                return {
                    "healthy": False,
                    "error": "OpenAI returned empty response"
                }
                
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return {
                "healthy": False,
                "error": f"OpenAI health check failed: {str(e)}"
            }
