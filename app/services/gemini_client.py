"""
Google Gemini API Client for Grammar Checking and Text Improvement
Advanced implementation with intelligent prompting and response handling
"""
import logging
import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import google.generativeai as genai

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
        
        # Initialize model with safety settings and structured output support
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH"
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
    
    def _create_gemini_schema(self) -> Dict[str, Any]:
        """
        Create a Gemini API compatible schema for structured output
        
        Returns:
            Schema dictionary compatible with Gemini API requirements
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
        
        base_prompt = """You are a professional editor and grammar expert. Analyze the provided text and return a comprehensive grammar analysis.

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

Please provide your analysis in the required structured format."""
        
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
  "correctedtext": "The grammatically corrected version of the text",
  "grammarissues": [
    {
      "issue": "Issue title",
      "explanation": "Detailed explanation of the grammar issue"
    }
  ],
  "speakingtips": ["List of specific suggestions for improving speaking and communication"]
}

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
    
    async def check_grammar_structured(
        self, 
        text: str, 
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check and correct grammar using structured output from Gemini API
        
        Args:
            text: Text to check for grammar errors
            context: Optional context for better corrections
            
        Returns:
            Dictionary with correction results using structured parsing:
            {
                "success": bool,
                "original_text": str,
                "corrected_text": str,
                "grammar_issues": List[Dict],
                "speaking_tips": List[str],
                "confidence_score": float,
                "improvements_made": int,
                "processing_time": float,
                "error": str (if failed)
            }
        """
        try:
            if not text or not text.strip():
                return {"success": False, "error": "Empty text provided"}
            
            logger.info(f"Starting structured grammar check for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            start_time = time.time()
            
            # Temporarily enable debug logging for structured output troubleshooting
            current_level = logger.level
            logger.setLevel(logging.DEBUG)
            
            # Create optimized prompt for structured output
            prompt = self._create_structured_grammar_prompt(text.strip(), context)
            
            # Generation config with structured output
            generation_config = {
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
                "response_mime_type": "application/json",
                "response_schema": self._create_gemini_schema()
            }
            
            # Generate response with structured output
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            processing_time = time.time() - start_time
            
            if not response:
                return {"success": False, "error": "No response from Gemini API"}
            
            # Extract and parse structured response with enhanced debugging
            try:
                raw_response = ""
                
                # Debug the response structure
                logger.debug(f"Response type: {type(response)}")
                logger.debug(f"Response has candidates: {hasattr(response, 'candidates')}")
                
                # Get the raw response text with more robust extraction
                if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    logger.debug(f"Candidate type: {type(candidate)}")
                    
                    # Check for finish_reason or safety issues
                    if hasattr(candidate, 'finish_reason'):
                        logger.debug(f"Candidate finish_reason: {candidate.finish_reason}")
                        if candidate.finish_reason and candidate.finish_reason != "STOP":
                            logger.warning(f"Candidate finished with reason: {candidate.finish_reason}")
                    
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts and len(candidate.content.parts) > 0:
                            part = candidate.content.parts[0]
                            if hasattr(part, 'text') and part.text:
                                raw_response = part.text.strip()
                                logger.debug(f"Extracted text from parts[0]: {len(raw_response)} chars")
                            else:
                                logger.warning("Part has no text attribute or text is empty")
                        else:
                            raw_response = str(candidate.content).strip()
                            logger.debug(f"Used candidate.content string: {len(raw_response)} chars")
                    else:
                        raw_response = str(candidate).strip()
                        logger.debug(f"Used candidate string: {len(raw_response)} chars")
                elif hasattr(response, 'text'):
                    raw_response = response.text.strip()
                    logger.debug(f"Used response.text: {len(raw_response)} chars")
                else:
                    raw_response = str(response).strip()
                    logger.debug(f"Used response string: {len(raw_response)} chars")
                
                logger.debug(f"Raw response preview: {raw_response[:100]}...")
                
                if not raw_response:
                    logger.error("Empty response from Gemini API - this might indicate content filtering or API issues")
                    return {"success": False, "error": "Empty response from Gemini API - possible content filtering"}
                
                # Parse the structured JSON response
                try:
                    parsed_response = json.loads(raw_response)
                    analysis = GrammarAnalysisResponse(**parsed_response)
                    
                    # Convert to output format - handle both direct JSON and Pydantic objects
                    grammar_issues_formatted = []
                    if isinstance(parsed_response.get("grammar_issues"), list):
                        for issue in parsed_response["grammar_issues"]:
                            if isinstance(issue, dict):
                                # Direct JSON format
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
                    # Fallback to legacy parsing if structured parsing fails
                    return await self._fallback_to_legacy_parsing(text, raw_response, processing_time)
                    
                except Exception as e:
                    logger.error(f"Error creating structured response: {e}")
                    return await self._fallback_to_legacy_parsing(text, raw_response, processing_time)
                    
            except Exception as parse_error:
                logger.error(f"Error parsing Gemini response: {parse_error}")
                return {"success": False, "error": f"Failed to parse Gemini response: {parse_error}"}
            
        except Exception as e:
            logger.error(f"Structured grammar check error: {e}", exc_info=True)
            return {
                "success": False, 
                "error": f"Grammar check failed: {str(e)}",
                "original_text": text
            }
        finally:
            # Restore original logging level
            if 'current_level' in locals():
                logger.setLevel(current_level)
    
    async def _fallback_to_legacy_parsing(self, text: str, raw_response: str, processing_time: float) -> Dict[str, Any]:
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
                
                # Clean up response that contains role metadata
                if raw_response.startswith('role: "model"'):
                    # Extract just the text content after the role metadata
                    lines = raw_response.split('\n')
                    content_lines = []
                    found_content = False
                    for line in lines:
                        line = line.strip()
                        if line.startswith('text:') or found_content:
                            if line.startswith('text:'):
                                # Remove 'text: "' prefix and handle the content
                                text_content = line[5:].strip()
                                if text_content.startswith('"'):
                                    text_content = text_content[1:]
                                content_lines.append(text_content)
                                found_content = True
                            elif line and not line.startswith('role:'):
                                content_lines.append(line)
                    
                    if content_lines:
                        # Join and clean up the content
                        raw_response = '\n'.join(content_lines).strip()
                        # Remove trailing quote if present
                        if raw_response.endswith('"'):
                            raw_response = raw_response[:-1]
                    
                # Log more details for debugging
                logger.info(f"Raw response (first 200 chars): {raw_response[:200]}...")
                
            except Exception as parse_error:
                logger.error(f"Error parsing Gemini response: {parse_error}")
                return {"success": False, "error": f"Failed to parse Gemini response: {parse_error}"}
            
            if advanced_mode:
                # Parse JSON response for advanced mode
                result = self._parse_advanced_response(raw_response, text)
            else:
                # Parse JSON response (new format)
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
        
        # Check if this looks like JSON - if so, reject it for simple cleaning
        if (cleaned.startswith('{') and cleaned.endswith('}')) or \
           ('```json' in cleaned) or \
           ('"correctedtext"' in cleaned and '"grammarissues"' in cleaned):
            logger.warning("Response appears to be JSON format, cannot clean as simple text")
            return "Grammar check unavailable - original text preserved"
        
        # Handle API response structure artifacts
        if 'role: "model"' in cleaned:
            # This looks like a raw API response, try to extract just the text
            lines = cleaned.split('\n')
            # Find lines that look like actual corrected text (not metadata)
            text_lines = []
            found_text_section = False
            for line in lines:
                line = line.strip()
                if line.startswith('text:'):
                    # Extract content after 'text: "'
                    text_content = line[5:].strip()
                    if text_content.startswith('"'):
                        text_content = text_content[1:]
                    if text_content.endswith('"'):
                        text_content = text_content[:-1]
                    text_lines.append(text_content)
                    found_text_section = True
                elif found_text_section and line and not line.startswith('role:') and not line.startswith('{') and not line.startswith('}'):
                    # Continue collecting text lines until we hit another metadata section
                    if line.endswith('"'):
                        line = line[:-1]
                    text_lines.append(line)
                elif found_text_section and (line.startswith('role:') or not line):
                    # End of text section
                    break
            
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
    
    def _extract_text_from_malformed_response(self, response_text: str, original_text: str) -> str:
        """
        Extract corrected text from a malformed JSON response
        
        Args:
            response_text: Raw response that failed JSON parsing
            original_text: Original text as fallback
            
        Returns:
            Extracted corrected text or original text if extraction fails
        """
        try:
            import re
            
            # Try to find text in "correctedtext" field
            patterns = [
                r'"correctedtext":\s*"([^"]*)"',
                r'"corrected_text":\s*"([^"]*)"',
                r'"corrected":\s*"([^"]*)"',
                # Handle multiline JSON with escaped quotes
                r'"correctedtext":\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
                r'"corrected_text":\s*"([^"\\]*(?:\\.[^"\\]*)*)"'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
                if match:
                    extracted = match.group(1)
                    # Basic cleaning of escape characters
                    extracted = extracted.replace('\\"', '"').replace('\\n', ' ').strip()
                    if extracted and len(extracted) > 10:  # Ensure it's substantial
                        logger.info(f"Extracted text from malformed JSON: {extracted[:100]}...")
                        return extracted
            
            # If no patterns match, try to clean the simple response
            cleaned = self._clean_simple_response(response_text)
            if cleaned and cleaned != "Grammar check unavailable - original text preserved":
                return cleaned
            
            # Final fallback
            logger.warning("Could not extract meaningful text from malformed response, returning original")
            return original_text
            
        except Exception as e:
            logger.error(f"Error extracting text from malformed response: {e}")
            return original_text
    
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
            
            # Debug logging to track what we extracted
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
            
            # Process grammar issues - handle both simple strings and complex objects
            if isinstance(grammar_issues, str):
                grammar_issues = [grammar_issues]
            elif isinstance(grammar_issues, list):
                processed_issues = []
                for issue in grammar_issues:
                    if isinstance(issue, dict):
                        # Handle complex issue format with explanation
                        issue_text = issue.get("issue", "")
                        explanation = issue.get("explanation", "")
                        if issue_text and explanation:
                            processed_issues.append(f"{issue_text}: {explanation}")
                        elif issue_text:
                            processed_issues.append(issue_text)
                    elif isinstance(issue, str):
                        processed_issues.append(issue)
                grammar_issues = processed_issues
            
            # Process speaking tips - handle different formats
            if isinstance(speaking_tips, str):
                speaking_tips = [speaking_tips]
            elif isinstance(speaking_tips, list):
                processed_tips = []
                for tip in speaking_tips:
                    if isinstance(tip, dict):
                        # Handle complex tip format
                        tip_text = tip.get("tip", "") or tip.get("suggestion", "") or str(tip)
                        processed_tips.append(tip_text)
                    elif isinstance(tip, str):
                        processed_tips.append(tip)
                speaking_tips = processed_tips
            
            return {
                "success": True,
                "original_text": original_text,
                "corrected_text": corrected_text,
                "grammar_issues": grammar_issues,
                "speaking_tips": speaking_tips,
                "processing_time": processing_time
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response, falling back to simple parsing: {e}")
            logger.debug(f"Raw response that failed to parse: {response_text[:500]}...")
            
            # Better fallback - try to extract text from the response even if it's malformed JSON
            corrected_text = self._extract_text_from_malformed_response(response_text, original_text)
            
            return {
                "success": True,
                "original_text": original_text,
                "corrected_text": corrected_text,
                "grammar_issues": ["Unable to analyze grammar issues - JSON parsing failed"],
                "speaking_tips": ["Try speaking more clearly and use complete sentences"],
                "processing_time": processing_time
            }
        except Exception as e:
            logger.error(f"Error parsing JSON response: {e}")
            return {
                "success": False,
                "error": f"Failed to parse response: {str(e)}",
                "original_text": original_text,
                "corrected_text": original_text,
                "processing_time": processing_time
            }
    
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
        max_retries: int = 4,
        retry_delay: float = 1.0,
        use_structured: bool = True
    ) -> Dict[str, Any]:
        """
        Check grammar with retry logic for better reliability
        
        Args:
            text: Text to check
            context: Optional context
            max_retries: Maximum retry attempts
            retry_delay: Initial delay between retries
            use_structured: Whether to use structured output (recommended)
            
        Returns:
            Grammar check result with retry information
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Grammar check attempt {attempt + 1}/{max_retries + 1}")
                
                # Use structured approach by default, fallback to legacy if needed
                if use_structured and attempt < 2:  # Try structured for first 2 attempts
                    result = await self.check_grammar_structured(text, context)
                else:
                    result = await self.check_grammar(text, context)
                
                if result.get("success"):
                    if attempt > 0:
                        logger.info(f"Grammar check succeeded after {attempt + 1} attempts")
                    result["retry_attempts"] = attempt
                    result["method_used"] = "structured" if (use_structured and attempt < 2) else "legacy"
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
            
            # Test structured output capability
            structured_support = await self._test_structured_output()
            
            return {
                "healthy": True,
                "api_accessible": True,
                "model": settings.gemini_model,
                "test_response": response_text,
                "structured_output_support": structured_support
            }
            
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return {
                "healthy": False,
                "api_accessible": False,
                "model": settings.gemini_model,
                "error": str(e)
            }
    
    async def _test_structured_output(self) -> bool:
        """
        Test if the API supports structured output with response schema
        
        Returns:
            True if structured output is supported, False otherwise
        """
        try:
            # Create a simple test schema
            test_prompt = "Respond with: corrected_text: 'Hello world', confidence_score: 0.95"
            
            # Try structured output
            test_config = {
                "temperature": 0.1,
                "max_output_tokens": 100,
                "response_mime_type": "application/json",
                "response_schema": self._create_gemini_schema()
            }
            
            test_response = await self.model.generate_content_async(
                test_prompt,
                generation_config=test_config
            )
            
            if test_response and test_response.candidates:
                logger.info("Structured output test: SUCCESS - API supports response schema")
                return True
            else:
                logger.warning("Structured output test: FAILED - No response received")
                return False
                
        except Exception as e:
            logger.warning(f"Structured output test: FAILED - {e}")
            return False
