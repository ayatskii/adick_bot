"""
ElevenLabs API Client for Speech-to-Text Transcription
Advanced implementation with retry logic, error handling, and multi-language support
"""
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import httpx
import requests
try:
    # Modern ElevenLabs API (v1.0+)
    from elevenlabs import generate, save, voices, set_api_key
    from elevenlabs.api import speech_to_text
    ElevenLabs = None  # Will use function-based API
except ImportError:
    try:
        # Try older client-based API
        from elevenlabs.client import ElevenLabs
    except ImportError:
        try:
            # Try even older API structure
            from elevenlabs import ElevenLabs
        except ImportError:
            # Final fallback
            import elevenlabs
            ElevenLabs = elevenlabs

from app.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsClient:
    """
    Comprehensive ElevenLabs API client for audio transcription
    
    Features:
    - Automatic retry with exponential backoff
    - Multi-language support with auto-detection
    - Speaker diarization and timestamps
    - Comprehensive error handling
    - Rate limit management
    """
    
    def __init__(self):
        """Initialize the ElevenLabs client with API credentials"""
        
        # Validate API key is present
        if not settings.elevenlabs_api_key or settings.elevenlabs_api_key == "your_key_here":
            raise ValueError("ElevenLabs API key is required. Set ELEVENLABS_API_KEY environment variable.")
        
        # Initialize ElevenLabs client based on available API
        if ElevenLabs is None:
            # Modern function-based API
            set_api_key(settings.elevenlabs_api_key)
            self.client = None  # Will use function calls directly
            self.use_modern_api = True
        else:
            # Legacy client-based API
            self.client = ElevenLabs(api_key=settings.elevenlabs_api_key)
            self.use_modern_api = False
            
        self.model_id = settings.elevenlabs_model
        
        # Debug: Log API type for troubleshooting
        logger.info(f"Using {'modern function-based' if self.use_modern_api else 'legacy client-based'} ElevenLabs API")
        if not self.use_modern_api and self.client:
            logger.info(f"Client methods: {[attr for attr in dir(self.client) if not attr.startswith('_')]}")
            if hasattr(self.client, 'speech_to_text'):
                logger.info(f"speech_to_text methods: {[attr for attr in dir(self.client.speech_to_text) if not attr.startswith('_')]}")
        
        # Rate limiting configuration
        self.requests_per_minute = 60  # Adjust based on your plan
        self.request_timestamps: List[float] = []
        
        logger.info(f"ElevenLabs client initialized with model: {self.model_id}")
    
    async def transcribe_audio(
        self, 
        file_path: str, 
        language_code: Optional[str] = None,
        enable_diarization: bool = True,
        enable_timestamps: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using ElevenLabs Scribe API
        
        Args:
            file_path: Path to the audio file
            language_code: Language hint (e.g., "en", "fr", "es") or "auto" for detection
            enable_diarization: Whether to identify different speakers
            enable_timestamps: Whether to include word-level timestamps
            
        Returns:
            Dict containing transcription results:
            {
                "success": bool,
                "text": str,
                "language": str,
                "processing_time": float,
                "speakers": List[Dict] (if diarization enabled),
                "timestamps": List[Dict] (if timestamps enabled),
                "error": str (if failed)
            }
        """
        try:
            # Validate input file
            if not Path(file_path).exists():
                return {"success": False, "error": f"Audio file not found: {file_path}"}
            
            # Check rate limits
            await self._check_rate_limits()
            
            logger.info(f"Starting transcription: {file_path}")
            start_time = time.time()
            
            # Prepare transcription parameters
            transcription_params = {
                "model_id": self.model_id,
                "language_code": language_code or "auto",
                "diarize": enable_diarization,
                "timestamp_granularity": "word" if enable_timestamps else None,
                "tag_audio_events": True,  # Tag laughs, music, etc.
            }
            
            # Remove None values
            transcription_params = {k: v for k, v in transcription_params.items() if v is not None}
            
            # Perform transcription (run in thread to avoid blocking)
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._transcribe_sync, 
                file_path, 
                transcription_params
            )
            
            processing_time = time.time() - start_time
            
            if result:
                logger.info(f"Transcription completed in {processing_time:.2f}s")
                
                # Parse the response
                transcription_result = {
                    "success": True,
                    "text": result.get("text", ""),
                    "language": result.get("language", "unknown"),
                    "processing_time": processing_time,
                    "confidence": result.get("confidence", 0.0),
                }
                
                # Add optional features if available
                if enable_diarization and "speakers" in result:
                    transcription_result["speakers"] = result["speakers"]
                
                if enable_timestamps and "timestamps" in result:
                    transcription_result["timestamps"] = result["timestamps"]
                
                if "audio_events" in result:
                    transcription_result["audio_events"] = result["audio_events"]
                
                return transcription_result
            else:
                return {"success": False, "error": "Empty response from ElevenLabs API"}
                
        except httpx.TimeoutException:
            logger.error("Transcription timeout - file may be too large")
            return {"success": False, "error": "Request timeout - try with a smaller file"}
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded")
                return {"success": False, "error": "Rate limit exceeded. Please try again later."}
            elif e.response.status_code == 401:
                logger.error("Invalid API key")
                return {"success": False, "error": "Invalid API key"}
            elif e.response.status_code == 413:
                logger.error("File too large")
                return {"success": False, "error": "Audio file is too large"}
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                return {"success": False, "error": f"API error: {e.response.status_code}"}
                
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {e}", exc_info=True)
            return {"success": False, "error": f"Transcription failed: {str(e)}"}
    
    def _transcribe_sync_BACKUP(self, file_path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """BACKUP - will be replaced"""
        pass
        
    def _transcribe_sync(self, file_path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Synchronous transcription method (called from thread executor)
        
        Args:
            file_path: Path to audio file
            params: Transcription parameters
            
        Returns:
            Transcription result dictionary or None if failed
        """
        # Simple implementation - just use the HTTP fallback method
        logger.info("Using HTTP fallback method for transcription")
        return self._transcribe_with_requests(file_path, params)
        try:
            with open(file_path, "rb") as audio_file:
                # Handle different API versions
                try:
                    if self.use_modern_api:
                        # Modern function-based API
                        logger.info("Using modern ElevenLabs function-based API")
                        try:
                            response = speech_to_text(
                                audio=audio_file,
                                model_id=params.get("model_id", self.model_id)
                            )
                        except NameError:
                            # speech_to_text function not available, try different approach
                            logger.warning("speech_to_text function not available, falling back to requests")
                            return self._transcribe_with_requests(file_path, params)
                    else:
                        # Legacy client-based API
                        logger.info("Using legacy ElevenLabs client-based API")
                        if hasattr(self.client, 'speech_to_text') and hasattr(self.client.speech_to_text, 'convert'):
                            response = self.client.speech_to_text.convert(
                                file=audio_file,
                                model_id=params.get("model_id", self.model_id)
                            )
                        elif hasattr(self.client, 'transcribe'):
                            response = self.client.transcribe(
                                audio=audio_file,
                                **params
                            )
                        else:
                            # Fallback to direct API call
                            logger.info("No client methods found, using direct API call")
                            return self._transcribe_with_requests(file_path, params)
                        
                except (AttributeError, TypeError, NameError) as e:
                    logger.info(f"Client method failed ({e}), using HTTP fallback")
                    return self._transcribe_with_requests(file_path, params)
                
                # If we get here, the API call was successful, process the response
                if hasattr(response, 'text'):
                    text = response.text
                elif isinstance(response, dict):
                    text = response.get('text', '')
                else:
                    text = str(response)
                
                return {
                    "text": text,
                    "language": "unknown", 
                    "confidence": 1.0,
                    "detected_language": "unknown"
                }
                
        except Exception as e:
            logger.error(f"Sync transcription error: {e}")
            return None
    async def transcribe_with_retry(
                            
                            # Add optional parameters
                            if params.get("language_code") and params["language_code"] != "auto":
                                data["language_code"] = params["language_code"]
                            
                            logger.info(f"Making direct API call with data: {data}")
                            response = requests.post(endpoint_url, headers=headers, files=files, data=data)
                            
                            # Log response details for debugging
                            logger.info(f"Response status: {response.status_code}")
                            logger.info(f"Response headers: {dict(response.headers)}")
                            if response.status_code != 200:
                                logger.error(f"Response content: {response.text}")
                                # Try to parse error message
                                try:
                                    error_data = response.json()
                                    logger.error(f"Parsed error: {error_data}")
                                except:
                                    pass
                            
                            response.raise_for_status()
                            response = response.json()
                            break  # Success, exit the loop
                            
                        except requests.exceptions.RequestException as e:
                            last_error = e
                            logger.warning(f"Endpoint {endpoint_url} failed: {e}")
                            continue
                    
                    # If all endpoints failed, raise the last error
                    if last_error:
                        raise last_error
                
                # Extract relevant data from response
                # Handle both object and dict responses
                if isinstance(response, dict):
                    # Direct API response (dict)
                    result = {
                        "text": response.get('text', ''),
                        "language": response.get('detected_language', 'unknown'),
                        "confidence": response.get('confidence', 0.0),
                    }
                else:
                    # Object response
                    result = {
                        "text": getattr(response, 'text', ''),
                        "language": getattr(response, 'detected_language', 'unknown'),
                        "confidence": getattr(response, 'confidence', 0.0),
                    }
                
                # Extract speaker information if available
                speakers_data = None
                if isinstance(response, dict):
                    speakers_data = response.get('speakers')
                elif hasattr(response, 'speakers'):
                    speakers_data = response.speakers
                
                if speakers_data:
                    if isinstance(speakers_data, list):
                        # Dict response format
                        result["speakers"] = speakers_data
                    else:
                        # Object response format
                        result["speakers"] = [
                            {
                                "speaker_id": speaker.id,
                                "segments": [
                                    {
                                        "text": segment.text,
                                        "start_time": segment.start,
                                        "end_time": segment.end
                                    }
                                    for segment in speaker.segments
                                ]
                            }
                            for speaker in speakers_data
                        ]
                
                # Extract timestamps if available
                words_data = None
                if isinstance(response, dict):
                    words_data = response.get('words')
                elif hasattr(response, 'words'):
                    words_data = response.words
                
                if words_data:
                    if isinstance(words_data, list):
                        # Dict response format
                        result["timestamps"] = words_data
                    else:
                        # Object response format
                        result["timestamps"] = [
                            {
                                "word": word.text,
                                "start": word.start,
                                "end": word.end,
                                "confidence": getattr(word, 'confidence', 1.0)
                            }
                            for word in words_data
                        ]
                
                # Extract audio events if available
                events_data = None
                if isinstance(response, dict):
                    events_data = response.get('events')
                elif hasattr(response, 'events'):
                    events_data = response.events
                
                if events_data:
                    if isinstance(events_data, list):
                        # Dict response format
                        result["audio_events"] = events_data
                    else:
                        # Object response format
                        result["audio_events"] = [
                            {
                                "type": event.type,
                                "start": event.start,
                                "end": event.end,
                                "description": getattr(event, 'description', '')
                            }
                            for event in events_data
                        ]
                
                return result
                
        except Exception as e:
            logger.error(f"Sync transcription error: {e}")
            raise e
    
    async def transcribe_with_retry(
        self, 
        file_path: str, 
        language_code: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Transcribe with intelligent retry logic and exponential backoff
        
        Args:
            file_path: Path to audio file
            language_code: Language hint
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (seconds)
            
        Returns:
            Transcription result with retry information
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Transcription attempt {attempt + 1}/{max_retries + 1}")
                
                result = await self.transcribe_audio(file_path, language_code)
                
                if result.get("success"):
                    if attempt > 0:
                        logger.info(f"Transcription succeeded after {attempt + 1} attempts")
                    result["retry_attempts"] = attempt
                    return result
                
                last_error = result.get("error", "Unknown error")
                
                # Don't retry certain types of errors
                non_retryable_errors = [
                    "Invalid API key",
                    "Audio file not found",
                    "File too large",
                    "Empty text provided"
                ]
                
                if any(err in last_error for err in non_retryable_errors):
                    logger.error(f"Non-retryable error: {last_error}")
                    break
                
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    delay = retry_delay * (2 ** attempt) + (asyncio.get_event_loop().time() % 1)
                    logger.warning(f"Attempt {attempt + 1} failed: {last_error}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt + 1} exception: {e}")
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
        
        # All attempts failed
        logger.error(f"All transcription attempts failed. Last error: {last_error}")
        return {
            "success": False,
            "error": f"Transcription failed after {max_retries + 1} attempts: {last_error}",
            "retry_attempts": max_retries + 1
        }
    
    async def _check_rate_limits(self):
        """Check and enforce rate limits"""
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < 60
        ]
        
        # Check if we're at the rate limit
        if len(self.request_timestamps) >= self.requests_per_minute:
            sleep_time = 60 - (current_time - self.request_timestamps[0])
            logger.warning(f"Rate limit reached. Waiting {sleep_time:.1f}s...")
            await asyncio.sleep(sleep_time)
            
        # Record this request
        self.request_timestamps.append(current_time)
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get dictionary of supported languages
        
        Returns:
            Dictionary mapping language codes to language names
        """
        # ElevenLabs Scribe supports 99+ languages
        return {
            "auto": "Auto-detect",
            "en": "English",
            "es": "Spanish", 
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese (Mandarin)",
            "ar": "Arabic",
            "hi": "Hindi",
            "nl": "Dutch",
            "pl": "Polish",
            "sv": "Swedish",
            "da": "Danish",
            "no": "Norwegian",
            "fi": "Finnish",
            "tr": "Turkish",
            "th": "Thai",
            "vi": "Vietnamese",
            "id": "Indonesian",
            "ms": "Malay",
            "uk": "Ukrainian",
            "cs": "Czech",
            "sk": "Slovak",
            "hu": "Hungarian",
            "ro": "Romanian",
            "bg": "Bulgarian",
            "hr": "Croatian",
            "sr": "Serbian",
            "sl": "Slovenian",
            "et": "Estonian",
            "lv": "Latvian",
            "lt": "Lithuanian",
            "mt": "Maltese",
            "ga": "Irish",
            "cy": "Welsh",
            "is": "Icelandic",
            "mk": "Macedonian",
            "sq": "Albanian",
            "eu": "Basque",
            "ca": "Catalan",
            "gl": "Galician",
            "fa": "Persian",
            "he": "Hebrew",
            "ur": "Urdu",
            "bn": "Bengali",
            "ta": "Tamil",
            "te": "Telugu",
            "ml": "Malayalam",
            "kn": "Kannada",
            "gu": "Gujarati",
            "pa": "Punjabi",
            "or": "Odia",
            "as": "Assamese",
            "ne": "Nepali",
            "si": "Sinhala",
            "my": "Burmese",
            "km": "Khmer",
            "lo": "Lao",
            "ka": "Georgian",
            "am": "Amharic",
            "sw": "Swahili",
            "yo": "Yoruba",
            "ig": "Igbo",
            "zu": "Zulu",
            "af": "Afrikaans",
            "xh": "Xhosa",
            "st": "Sesotho",
            "tn": "Setswana",
            "ts": "Tsonga",
            "ss": "Swati",
            "ve": "Venda",
            "nr": "Ndebele",
        }
    
    def _transcribe_with_requests(self, file_path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Simple HTTP-based transcription fallback method
        
        Args:
            file_path: Path to audio file
            params: Transcription parameters
            
        Returns:
            Transcription result dictionary or None if failed
        """
        try:
            import requests
            
            with open(file_path, "rb") as audio_file:
                # ElevenLabs speech-to-text API endpoint
                url = "https://api.elevenlabs.io/v1/speech-to-text"
                
                headers = {
                    "xi-api-key": settings.elevenlabs_api_key
                }
                
                files = {
                    "file": ("audio.ogg", audio_file, "audio/ogg")
                }
                
                data = {
                    "model_id": params.get("model_id", self.model_id)
                }
                
                # Add language code if specified
                if params.get("language_code") and params["language_code"] != "auto":
                    data["language_code"] = params["language_code"]
                
                logger.info(f"Making HTTP request to {url}")
                response = requests.post(url, headers=headers, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "text": result.get("text", ""),
                        "language": result.get("language", "unknown"),
                        "confidence": result.get("confidence", 0.0),
                        "detected_language": result.get("detected_language", "unknown")
                    }
                else:
                    logger.error(f"HTTP request failed: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"HTTP fallback transcription failed: {e}")
            return None

    async def check_api_health(self) -> Dict[str, Any]:
        """
        Check ElevenLabs API health and account status
        
        Returns:
            Dictionary with health status and account information
        """
        try:
            # Get user information (requires valid API key)
            user_info = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.client.user.get()
            )
            
            return {
                "healthy": True,
                "api_accessible": True,
                "subscription": getattr(user_info, 'subscription', 'unknown'),
                "character_limit": getattr(user_info, 'character_limit', 0),
                "character_count": getattr(user_info, 'character_count', 0),
                "can_use_instant_voice_cloning": getattr(user_info, 'can_use_instant_voice_cloning', False),
                "model": self.model_id
            }
            
        except Exception as e:
            logger.error(f"ElevenLabs health check failed: {e}")
            return {
                "healthy": False,
                "api_accessible": False,
                "error": str(e),
                "model": self.model_id
            }
