"""
Google Vertex AI Client for Grammar Checking and Text Improvement
Advanced implementation with intelligent prompting and response handling using Vertex AI
"""
import logging
import asyncio
import time
import json
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Vertex AI imports
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    HarmCategory,
    HarmBlockThreshold,
    Content,
    Part
)

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
    Advanced Vertex AI client for grammar checking and text improvement
    
    Features:
    - Context-aware grammar correction
    - Multiple correction strategies
    - Intelligent prompt engineering
    - Retry logic with backoff
    - Response validation and cleaning
    """
    
    def __init__(self):
        """Initialize Vertex AI client with GCP credentials"""
        
        # Validate GCP project configuration
        if not settings.gcp_project_id:
            raise ValueError("GCP Project ID is required. Set GCP_PROJECT_ID environment variable.")
        
        # Initialize Vertex AI
        try:
            # If credentials path is provided, use it
            if settings.gcp_credentials_path:
                # Convert relative path to absolute path
                credentials_path = os.path.abspath(settings.gcp_credentials_path)
                if os.path.exists(credentials_path):
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                    logger.info(f"Using service account credentials from: {credentials_path}")
                else:
                    logger.warning(f"Credentials file not found at: {credentials_path}")
            
            # Initialize Vertex AI with project and location
            vertexai.init(
                project=settings.gcp_project_id,
                location=settings.gcp_location
            )
            
            logger.info(f"Vertex AI initialized - Project: {settings.gcp_project_id}, Location: {settings.gcp_location}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            raise ValueError(f"Vertex AI initialization failed: {e}")
        
        # Initialize model with safety settings
        self.model = GenerativeModel(
            model_name=settings.vertex_model,
        )
        
        # Safety settings - using Vertex AI format
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        
        # Generation configuration for consistent results
        self.generation_config = GenerationConfig(
            temperature=0.1,  # Low temperature for consistent grammar correction
            top_p=0.8,
            top_k=40,
            max_output_tokens=4096,
        )
        
        logger.info(f"Vertex AI client initialized with model: {settings.vertex_model}")
    
    def _create_gemini_schema(self) -> Dict[str, Any]:
        """
        Create a Vertex AI compatible schema for structured output
        
        Returns:
            Schema dictionary compatible with Vertex AI requirements
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
        Check and correct grammar using structured output from Vertex AI
        
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
            
            # Try structured output first, with fallback to JSON-only mode
            try:
                # Generation config with structured output
                generation_config = GenerationConfig(
                    temperature=0.1,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                    response_schema=self._create_gemini_schema()
                )
                
                logger.debug("Attempting structured output with schema")
            except Exception as schema_error:
                logger.warning(f"Schema creation failed, falling back to JSON-only mode: {schema_error}")
                # Fallback to JSON without schema
                generation_config = GenerationConfig(
                    temperature=0.1,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=4096,
                    response_mime_type="application/json"
                )
            
            # Generate response with structured output
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=generation_config,
                safety_settings=self.safety_settings
            )
            
            processing_time = time.time() - start_time
            
            if not response:
                return {"success": False, "error": "No response from Vertex AI"}
            
            # Extract and parse structured response
            try:
                # Get the response text
                raw_response = response.text.strip()
                
                logger.debug(f"Raw response preview: {raw_response[:100]}...")
                
                if not raw_response:
                    logger.error("Empty response from Vertex AI")
                    return {"success": False, "error": "Empty response from Vertex AI"}
                
                # Parse the structured JSON response
                try:
                    parsed_response = json.loads(raw_response)
                    analysis = GrammarAnalysisResponse(**parsed_response)
                    
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
                    return await self._fallback_to_legacy_parsing(text, raw_response, processing_time)
                    
                except Exception as e:
                    logger.error(f"Error creating structured response: {e}")
                    return await self._fallback_to_legacy_parsing(text, raw_response, processing_time)
                    
            except Exception as parse_error:
                logger.error(f"Error parsing Vertex AI response: {parse_error}")
                return {"success": False, "error": f"Failed to parse Vertex AI response: {parse_error}"}
            
        except Exception as e:
            logger.error(f"Structured grammar check error: {e}", exc_info=True)
            return {
                "success": False, 
                "error": f"Grammar check failed: {str(e)}",
                "original_text": text
            }
    
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
            Dictionary with correction results
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
            
            # Generate response using Vertex AI
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            
            processing_time = time.time() - start_time
            
            if not response:
                return {"success": False, "error": "No response from Vertex AI"}
            
            # Extract response text
            try:
                raw_response = response.text.strip()
                    
                if not raw_response:
                    return {"success": False, "error": "Empty response text from Vertex AI"}
                
                logger.info(f"Raw response (first 200 chars): {raw_response[:200]}...")
                
            except Exception as parse_error:
                logger.error(f"Error parsing Vertex AI response: {parse_error}")
                return {"success": False, "error": f"Failed to parse Vertex AI response: {parse_error}"}
            
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
        if not cleaned or len(cleaned.strip()) < 10:
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
                    if extracted and len(extracted) > 10:
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
            logger.warning(f"JSON parsing failed: {e}. Attempting text extraction from malformed JSON.")
            corrected_text = self._extract_text_from_malformed_response(response_text, original_text)
            
            return {
                "success": True,
                "original_text": original_text,
                "corrected_text": corrected_text,
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
    
    def _parse_advanced_response(self, response_text: str, original_text: str) -> Dict[str, Any]:
        """
        Parse advanced mode response with detailed change tracking
        
        Args:
            response_text: Raw JSON response
            original_text: Original input text
            
        Returns:
            Parsed response with detailed changes
        """
        try:
            import json
            import re
            
            # Clean and extract JSON
            cleaned = response_text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = cleaned
            
            parsed = json.loads(json_str)
            
            return {
                "success": True,
                "original_text": original_text,
                "corrected_text": parsed.get("corrected_text", original_text),
                "changes_made": parsed.get("changes_made", []),
                "confidence_score": parsed.get("confidence_score", 0.90),
                "text_quality": parsed.get("text_quality", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Error parsing advanced response: {e}")
            return {
                "success": False,
                "error": f"Failed to parse advanced response: {str(e)}",
                "original_text": original_text
            }
    
    async def check_api_health(self) -> Dict[str, Any]:
        """
        Check if the Vertex AI API is accessible and healthy
        
        Returns:
            Dictionary with health status
        """
        try:
            # Try a simple generation request
            test_text = "Hello world"
            response = await asyncio.to_thread(
                self.model.generate_content,
                f"Say 'OK' if you can read this: {test_text}",
                generation_config=GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=10
                )
            )
            
            if response and response.text:
                return {
                    "healthy": True,
                    "message": "Vertex AI API is accessible",
                    "model": settings.vertex_model,
                    "project": settings.gcp_project_id,
                    "location": settings.gcp_location
                }
            else:
                return {
                    "healthy": False,
                    "error": "Vertex AI returned empty response"
                }
                
        except Exception as e:
            logger.error(f"Vertex AI health check failed: {e}")
            return {
                "healthy": False,
                "error": f"Vertex AI health check failed: {str(e)}"
            }
