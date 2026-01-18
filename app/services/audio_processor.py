"""
Main audio processing service that coordinates transcription and grammar checking
"""
import logging
import os
from typing import Dict, Any
from telegram import Message

from app.config import settings
from app.services.elevenlabs_client import ElevenLabsClient
from app.services.openai_client import OpenAIClient
from app.utils.file_handler import FileHandler

logger = logging.getLogger(__name__)

class AudioProcessor:
    """
    Main service that orchestrates the complete audio processing pipeline:
    1. Download audio from Telegram
    2. Transcribe using ElevenLabs
    3. Check grammar using OpenAI
    4. Return results to user
    """
    
    def __init__(self):
        """Initialize the audio processor with all required clients"""
        self.elevenlabs_client = ElevenLabsClient()
        self.openai_client = OpenAIClient()
        self.file_handler = FileHandler()
        
        logger.info("Audio processor initialized with ElevenLabs and OpenAI clients")
    
    async def process_audio_message(self, message: Message) -> Dict[str, Any]:
        """
        Process a complete audio message from Telegram
        
        Args:
            message: Telegram message containing audio
            
        Returns:
            Dictionary with processing results:
            {
                "success": bool,
                "original_text": str,
                "corrected_text": str,
                "language": str,
                "processing_time": float,
                "file_info": Dict,
                "error": str (if failed)
            }
        """
        audio_file_path = None
        
        try:
            logger.info("Starting audio message processing")
            
            # Step 1: Download and validate audio file
            audio_file_path = await self._download_audio_file(message)
            if not audio_file_path:
                return {"success": False, "error": "Failed to download audio file"}
            
            # Step 2: Validate the audio file
            validation_result = self.file_handler.validate_audio_file(audio_file_path)
            if not validation_result["valid"]:
                return {"success": False, "error": validation_result["error"]}
            
            # Step 3: Transcribe audio using ElevenLabs
            logger.info("Starting audio transcription...")
            transcription_result = await self.elevenlabs_client.transcribe_with_retry(
                file_path=audio_file_path,
                language_code="auto",  # Auto-detect language
                max_retries=2
            )
            
            if not transcription_result.get("success"):
                return {
                    "success": False, 
                    "error": f"Transcription failed: {transcription_result.get('error')}"
                }
            
            original_text = transcription_result.get("text", "").strip()
            if not original_text:
                return {"success": False, "error": "No speech detected in audio file"}
            
            # Step 4: Check grammar using OpenAI
            logger.info("Starting grammar check...")
            grammar_result = await self.openai_client.check_grammar_with_retry(
                text=original_text,
                context="transcribed_speech",
                max_retries=2
            )
            
            # Even if grammar check fails, we still return the transcription
            if grammar_result.get("success"):
                corrected_text = grammar_result.get("corrected_text", original_text)
            else:
                logger.warning(f"Grammar check failed: {grammar_result.get('error')}")
                corrected_text = original_text
            
            # Step 5: Compile final results
            result = {
                "success": True,
                "original_text": original_text,
                "corrected_text": corrected_text,
            }
            
            # Add OpenAI grammar analysis data if available
            if grammar_result.get("success"):
                result["grammar_issues"] = grammar_result.get("grammar_issues", [])
                result["speaking_tips"] = grammar_result.get("speaking_tips", [])
            
            # Add optional features if available
            if "speakers" in transcription_result:
                result["speakers"] = transcription_result["speakers"]
            
            if "audio_events" in transcription_result:
                result["audio_events"] = transcription_result["audio_events"]
            
            logger.info("Audio processing completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error processing audio message: {e}", exc_info=True)
            return {"success": False, "error": f"Processing failed: {str(e)}"}
        
        finally:
            # Always clean up the temporary audio file
            if audio_file_path:
                self.file_handler.cleanup_file(audio_file_path)
    
    async def _download_audio_file(self, message: Message) -> str:
        """
        Download audio file from Telegram message
        
        Args:
            message: Telegram message containing audio
            
        Returns:
            Path to downloaded file or None if failed
        """
        try:
            # Determine the audio file object and extension
            audio_file = None
            file_extension = ".ogg"  # Default for voice messages
            
            if message.voice:
                audio_file = message.voice
                file_extension = ".ogg"
            elif message.audio:
                audio_file = message.audio
                file_extension = self._get_file_extension(message.audio.file_name) or ".mp3"
            elif message.document and message.document.mime_type and "audio" in message.document.mime_type:
                audio_file = message.document
                file_extension = self._get_file_extension(message.document.file_name) or ".mp3"
            
            if not audio_file:
                logger.error("No audio file found in message")
                return None
            
            # Create temporary file
            temp_file_path = self.file_handler.create_temp_file(
                suffix=file_extension,
                prefix="telegram_audio_"
            )
            
            # Download the file
            telegram_file = await audio_file.get_file()
            await telegram_file.download_to_drive(temp_file_path)
            
            logger.info(f"Audio file downloaded: {temp_file_path} ({os.path.getsize(temp_file_path)} bytes)")
            return temp_file_path
            
        except Exception as e:
            logger.error(f"Error downloading audio file: {e}")
            return None
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        if not filename:
            return ".ogg"
        
        _, ext = os.path.splitext(filename.lower())
        return ext if ext else ".ogg"
    
    async def get_processing_status(self) -> Dict[str, Any]:
        """
        Get status of all processing components
        
        Returns:
            Status dictionary with health information
        """
        # Check ElevenLabs health
        elevenlabs_health = await self.elevenlabs_client.check_api_health()
        
        # Check OpenAI health
        openai_health = await self.openai_client.check_api_health()
        
        # Get file handler stats
        file_stats = self.file_handler.get_directory_stats()
        
        return {
            "elevenlabs": elevenlabs_health,
            "openai": openai_health,
            "file_handler": file_stats,
            "overall_status": "healthy" if (
                elevenlabs_health.get("healthy") and 
                openai_health.get("healthy")
            ) else "degraded"
        }
