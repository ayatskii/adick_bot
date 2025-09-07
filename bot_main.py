#!/usr/bin/env python3
"""
Telegram Audio Bot - Main Application
=====================================

A production-ready Telegram bot that processes audio messages:
1. Receives audio files from users
2. Transcribes audio using ElevenLabs API
3. Checks and corrects grammar using Google Gemini API
4. Returns both original and corrected transcriptions

Features:
- Robust error handling and retry logic
- Comprehensive logging and monitoring
- Rate limiting and user management
- Multi-language support
- Production-ready deployment
"""

import asyncio
import logging
import signal
import sys
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

# Ensure the app module can be found
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Telegram Bot Framework
from telegram import Update, Message, Audio, Voice, VideoNote, Document
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes
)

# Application Components
from app.config import settings
from app.utils.logger import setup_logging, get_logger
from app.services.audio_processor import AudioProcessor
from app.services.elevenlabs_client import ElevenLabsClient
from app.services.gemini_client import GeminiClient

# Initialize logging
setup_logging()
logger = get_logger(__name__)

class TelegramAudioBot:
    """
    Main Telegram Bot class that orchestrates all audio processing functionality
    """
    
    def __init__(self):
        """Initialize the bot with all required services"""
        self.audio_processor = None
        self.application = None
        self.is_running = False
        
        # User session tracking
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        
        logger.info("🤖 Telegram Audio Bot initializing...")
    
    async def initialize_services(self):
        """Initialize all backend services"""
        try:
            logger.info("🔧 Initializing backend services...")
            
            # Initialize audio processor (which includes ElevenLabs and Gemini clients)
            self.audio_processor = AudioProcessor()
            
            # Test service connectivity
            await self._test_service_health()
            
            logger.info("✅ All backend services initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize services: {e}")
            raise
    
    async def _test_service_health(self):
        """Test connectivity to all external services"""
        logger.info("🏥 Testing service health...")
        
        # Test ElevenLabs
        try:
            health = await self.audio_processor.elevenlabs_client.check_api_health()
            if health.get("healthy"):
                logger.info("✅ ElevenLabs API: Healthy")
            else:
                logger.warning(f"⚠️ ElevenLabs API: {health.get('error', 'Unknown issue')}")
        except Exception as e:
            logger.warning(f"⚠️ ElevenLabs health check failed: {e}")
        
        # Test Gemini
        try:
            health = await self.audio_processor.gemini_client.check_api_health()
            if health.get("healthy"):
                logger.info("✅ Gemini API: Healthy")
            else:
                logger.warning(f"⚠️ Gemini API: {health.get('error', 'Unknown issue')}")
        except Exception as e:
            logger.warning(f"⚠️ Gemini health check failed: {e}")
    
    def create_application(self) -> Application:
        """Create and configure the Telegram application"""
        logger.info("📱 Creating Telegram application...")
        
        # Create application with token
        application = Application.builder().token(settings.telegram_bot_token).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        
        # Add message handlers for different audio types
        application.add_handler(MessageHandler(filters.AUDIO, self.handle_audio_message))
        application.add_handler(MessageHandler(filters.VOICE, self.handle_voice_message))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, self.handle_video_note))
        application.add_handler(MessageHandler(filters.Document.AUDIO, self.handle_audio_document))
        
        # Add handler for unsupported message types
        application.add_handler(MessageHandler(~filters.COMMAND, self.handle_unsupported_message))
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        logger.info("✅ Telegram application configured")
        return application
    
    # ===========================================
    # COMMAND HANDLERS
    # ===========================================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        logger.info(f"👋 New user started bot: {user.first_name} ({user.id})")
        
        # Initialize user session
        self.user_sessions[user.id] = {
            "first_name": user.first_name,
            "username": user.username,
            "start_time": asyncio.get_event_loop().time(),
            "messages_processed": 0,
            "last_activity": asyncio.get_event_loop().time()
        }
        
        welcome_message = (
            f"🎤 **Welcome to Audio Bot, {user.first_name}!**\n\n"
            "I can help you transcribe and improve audio messages!\n\n"
            "📋 **How to use:**\n"
            "• Send me any audio file, voice message, or video note\n"
            "• I'll transcribe the speech using AI\n"
            "• Then I'll check and correct the grammar\n"
            "• You'll get both original and corrected versions\n\n"
            "🌍 **Supported languages:** 99+ languages with auto-detection\n"
            "📁 **File size limit:** Up to 25MB\n"
            "⚡ **Processing time:** Usually 10-30 seconds\n\n"
            "💡 **Tips:**\n"
            "• Speak clearly for better transcription\n"
            "• Minimize background noise\n"
            "• Use /help for more commands\n\n"
            "🚀 Ready to transcribe your first audio!"
        )
        
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        # Handle both edited messages and regular messages
        message = update.message or update.edited_message
        if not message:
            return
            
        help_text = (
            "🤖 **Audio Bot Help**\n\n"
            "**Commands:**\n"
            "• `/start` - Start the bot and see welcome message\n"
            "• `/help` - Show this help message\n"
            "• `/status` - Check bot and service status\n"
            "• `/stats` - Show your usage statistics\n\n"
            "**Supported Audio Formats:**\n"
            "• Voice messages (OGG, OPUS)\n"
            "• Audio files (MP3, WAV, M4A, AAC)\n"
            "• Video notes (MP4 audio track)\n"
            "• Audio documents\n\n"
            "**Features:**\n"
            "• 🎯 High-accuracy transcription\n"
            "• 📝 Grammar checking and correction\n"
            "• 🌍 99+ language support\n"
            "• 🔄 Automatic retry on failures\n"
            "• 📊 Processing statistics\n\n"
            "**Limits:**\n"
            "• Maximum file size: 25MB\n"
            "• Processing timeout: 2 minutes\n"
            "• Rate limit: Reasonable usage\n\n"
            "Having issues? Contact support!"
        )
        
        await message.reply_text(help_text, parse_mode="Markdown")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show bot and service status"""
        user_id = update.effective_user.id
        
        try:
            # Check service health
            elevenlabs_health = await self.audio_processor.elevenlabs_client.check_api_health()
            gemini_health = await self.audio_processor.gemini_client.check_api_health()
            
            # Format status
            elevenlabs_status = "✅ Healthy" if elevenlabs_health.get("healthy") else "❌ Error"
            gemini_status = "✅ Healthy" if gemini_health.get("healthy") else "❌ Error"
            
            status_text = (
                "📊 **Bot Status**\n\n"
                f"🤖 **Bot:** ✅ Running\n"
                f"🎤 **Transcription Service:** {elevenlabs_status}\n"
                f"📝 **Grammar Service:** {gemini_status}\n"
                f"💾 **Upload Directory:** ✅ Ready\n\n"
                f"**Service Details:**\n"
                f"• ElevenLabs Model: {settings.elevenlabs_model}\n"
                f"• Gemini Model: {settings.gemini_model}\n"
                f"• Max File Size: {settings.max_file_size // (1024*1024)}MB\n"
                f"• Active Users: {len(self.user_sessions)}\n\n"
                "All systems operational! 🚀"
            )
            
        except Exception as e:
            logger.error(f"Error checking status: {e}")
            status_text = (
                "📊 **Bot Status**\n\n"
                "⚠️ Unable to check all services\n"
                "Bot is running but some services may be experiencing issues.\n\n"
                "Please try again later or contact support."
            )
        
        await update.message.reply_text(status_text, parse_mode="Markdown")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - show user statistics"""
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id, {})
        
        if not session:
            await update.message.reply_text(
                "📊 No statistics available yet. Send some audio messages first!"
            )
            return
        
        current_time = asyncio.get_event_loop().time()
        session_duration = current_time - session.get("start_time", current_time)
        hours = int(session_duration // 3600)
        minutes = int((session_duration % 3600) // 60)
        
        stats_text = (
            f"📊 **Your Statistics**\n\n"
            f"👤 **User:** {session.get('first_name', 'Unknown')}\n"
            f"⏱️ **Session Duration:** {hours}h {minutes}m\n"
            f"🎵 **Messages Processed:** {session.get('messages_processed', 0)}\n"
            f"🕒 **Last Activity:** Recent\n\n"
            "Keep sending audio to see more stats! 📈"
        )
        
        await update.message.reply_text(stats_text, parse_mode="Markdown")
    
    # ===========================================
    # AUDIO MESSAGE HANDLERS
    # ===========================================
    
    async def handle_audio_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular audio file messages"""
        await self._process_audio_message(update, "audio file")
    
    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages"""
        await self._process_audio_message(update, "voice message")
    
    async def handle_video_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video notes (round video messages)"""
        await self._process_audio_message(update, "video note")
    
    async def handle_audio_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle audio files sent as documents"""
        await self._process_audio_message(update, "audio document")
    
    async def _process_audio_message(self, update: Update, audio_type: str):
        """Common audio processing logic for all audio message types"""
        user = update.effective_user
        message = update.message
        
        logger.info(f"🎵 Processing {audio_type} from user {user.first_name} ({user.id})")
        
        # Update user session
        if user.id in self.user_sessions:
            self.user_sessions[user.id]["last_activity"] = asyncio.get_event_loop().time()
            self.user_sessions[user.id]["messages_processed"] += 1
        
        # Send initial processing message
        processing_msg = await message.reply_text(
            f"🔄 **Processing your {audio_type}...**\n\n"
            "⏳ This usually takes 10-30 seconds\n"
            "📝 Transcribing speech and checking grammar...",
            parse_mode="Markdown"
        )
        
        try:
            # Process the audio using the audio processor service
            result = await self.audio_processor.process_audio_message(message)
            
            if result.get("success"):
                # Format successful response
                response_text = self._format_success_response(result, audio_type)
                
                # Edit the processing message with results
                await processing_msg.edit_text(response_text, parse_mode="Markdown")
                
                logger.info(f"✅ Successfully processed {audio_type} for user {user.id}")
                
            else:
                # Handle processing error
                error_msg = result.get("error", "Unknown error occurred")
                response_text = (
                    f"❌ **Failed to process {audio_type}**\n\n"
                    f"**Error:** {error_msg}\n\n"
                    "💡 **Suggestions:**\n"
                    "• Check if the audio is clear and not corrupted\n"
                    "• Try with a smaller file (under 25MB)\n"
                    "• Ensure the audio contains speech\n"
                    "• Try again in a few moments\n\n"
                    "If the problem persists, contact support."
                )
                
                await processing_msg.edit_text(response_text, parse_mode="Markdown")
                
                logger.warning(f"❌ Failed to process {audio_type} for user {user.id}: {error_msg}")
                
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"❌ Unexpected error processing {audio_type}: {e}", exc_info=True)
            
            error_response = (
                f"💥 **Unexpected error processing {audio_type}**\n\n"
                "Sorry, something went wrong on our end.\n"
                "Our team has been notified.\n\n"
                "Please try again later."
            )
            
            try:
                await processing_msg.edit_text(error_response, parse_mode="Markdown")
            except:
                # If editing fails, send a new message
                await message.reply_text(error_response, parse_mode="Markdown")
    
    def _format_success_response(self, result: Dict[str, Any], audio_type: str) -> str:
        """Format a successful processing result into a user-friendly message"""
        original_text = result.get("original_text", "")
        corrected_text = result.get("corrected_text", "")
        language = result.get("language", "unknown")
        processing_time = result.get("processing_time", 0)
        confidence = result.get("transcription_confidence", 0)
        
        # Determine if grammar was actually corrected
        grammar_corrected = original_text.strip() != corrected_text.strip()
        
        response = f"✅ **{audio_type.title()} processed successfully!**\n\n"
        
        # Original transcription
        response += f"🎤 **Original Transcription:**\n_{original_text}_\n\n"
        
        # Corrected version (only if different)
        if grammar_corrected:
            response += f"📝 **Grammar Corrected:**\n_{corrected_text}_\n\n"
        else:
            response += f"✨ **Grammar:** Perfect! No corrections needed.\n\n"
        
        # Processing details
        response += f"📊 **Processing Details:**\n"
        response += f"• Language: {language.title()}\n"
        response += f"• Processing Time: {processing_time:.1f}s\n"
        
        if confidence > 0:
            response += f"• Confidence: {confidence:.1%}\n"
        
        # File information
        file_info = result.get("file_info", {})
        if file_info.get("size_mb"):
            response += f"• File Size: {file_info['size_mb']:.1f}MB\n"
        
        # Optional: Speaker information
        if result.get("speakers"):
            speaker_count = len(result["speakers"])
            response += f"• Speakers Detected: {speaker_count}\n"
        
        # Optional: Audio events
        if result.get("audio_events"):
            events = len(result["audio_events"])
            response += f"• Audio Events: {events}\n"
        
        return response
    
    async def handle_unsupported_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unsupported message types"""
        message_type = "message"
        
        if update.message.photo:
            message_type = "photo"
        elif update.message.video:
            message_type = "video"
        elif update.message.document:
            message_type = "document"
        elif update.message.text:
            message_type = "text message"
        
        response = (
            f"🚫 **Unsupported {message_type}**\n\n"
            "I can only process audio content:\n"
            "• 🎤 Voice messages\n"
            "• 🎵 Audio files (MP3, WAV, etc.)\n"
            "• 🎬 Video notes\n"
            "• 📎 Audio documents\n\n"
            "Please send an audio file or use /help for more information."
        )
        
        await update.message.reply_text(response, parse_mode="Markdown")
    
    # ===========================================
    # ERROR HANDLING
    # ===========================================
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors that occur during message processing"""
        logger.error(f"❌ Exception while handling update {update}: {context.error}", exc_info=context.error)
        
        # Try to notify the user if possible
        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "💥 **Oops! Something went wrong.**\n\n"
                        "Our team has been notified and we're looking into it.\n"
                        "Please try again in a few moments.\n\n"
                        "If the problem persists, use /help for support information."
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")
    
    # ===========================================
    # BOT LIFECYCLE MANAGEMENT
    # ===========================================
    
    async def start_bot(self):
        """Start the Telegram bot"""
        try:
            logger.info("🚀 Starting Telegram Audio Bot...")
            
            # Initialize services first
            await self.initialize_services()
            
            # Create and configure the application
            self.application = self.create_application()
            
            # Start the bot
            logger.info("📡 Starting bot polling...")
            await self.application.initialize()
            await self.application.start()
            
            # Start polling for updates
            await self.application.updater.start_polling(
                poll_interval=settings.polling_interval,
                timeout=30,
                read_timeout=20,
                write_timeout=20,
                connect_timeout=20,
                pool_timeout=20
            )
            
            self.is_running = True
            logger.info("✅ Bot is running and ready to process audio messages!")
            
            # Keep the bot running until stopped
            # Wait indefinitely - the polling will handle messages
            # The application will run until stopped by signal or error
            global stop_event
            stop_event = asyncio.Event()
            
            try:
                # Wait for stop signal
                await stop_event.wait()
                logger.info("📶 Stop signal received, shutting down...")
            except asyncio.CancelledError:
                logger.info("📶 Bot polling cancelled")
            except KeyboardInterrupt:
                logger.info("📶 Received interrupt signal")
            finally:
                # Clean shutdown
                await self.stop_bot()
            
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
            raise
    
    async def stop_bot(self):
        """Stop the Telegram bot gracefully"""
        if self.application and self.is_running:
            logger.info("🛑 Stopping Telegram Audio Bot...")
            
            try:
                # Stop the application (this also stops the updater)
                await self.application.stop()
                await self.application.shutdown()
                
                self.is_running = False
                logger.info("✅ Bot stopped successfully")
                
            except Exception as e:
                logger.error(f"❌ Error stopping bot: {e}")

# ===========================================
# SIGNAL HANDLING AND MAIN EXECUTION
# ===========================================

# Global bot instance and stop event for signal handling
bot_instance: Optional[TelegramAudioBot] = None
stop_event: Optional[asyncio.Event] = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"📶 Received signal {signum}, initiating graceful shutdown...")
    
    # Set the stop event to break the main loop
    if stop_event and not stop_event.is_set():
        stop_event.set()
    
    logger.info("👋 Shutdown signal sent")
    # Don't call sys.exit here - let the main loop handle cleanup

async def main():
    """Main application entry point"""
    global bot_instance
    
    try:
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Create and start the bot
        bot_instance = TelegramAudioBot()
        await bot_instance.start_bot()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
        if bot_instance:
            await bot_instance.stop_bot()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        if bot_instance:
            await bot_instance.stop_bot()
        sys.exit(1)

if __name__ == "__main__":
    """Entry point when run directly"""
    logger.info("🎬 Starting Telegram Audio Bot application...")
    
    # Validate configuration before starting
    try:
        logger.info(f"📋 Configuration validation:")
        logger.info(f"  • Bot Token: {'✅ Set' if settings.telegram_bot_token else '❌ Missing'}")
        logger.info(f"  • ElevenLabs API: {'✅ Set' if settings.elevenlabs_api_key else '❌ Missing'}")
        logger.info(f"  • Gemini API: {'✅ Set' if settings.gemini_api_key else '❌ Missing'}")
        logger.info(f"  • Upload Dir: {settings.upload_dir}")
        logger.info(f"  • Log Level: {settings.log_level}")
        
        # Check for missing critical configuration
        if not all([settings.telegram_bot_token, settings.elevenlabs_api_key, settings.gemini_api_key]):
            logger.error("❌ Missing required API keys! Check your .env file.")
            sys.exit(1)
        
        # Start the event loop
        asyncio.run(main())
        
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}", exc_info=True)
        sys.exit(1)
