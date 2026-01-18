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

# Add app directory to path if it exists
app_dir = os.path.join(current_dir, 'app')
if os.path.exists(app_dir) and app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Telegram Bot Framework
from telegram import Update, Message, Audio, Voice, VideoNote, Document
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes
)
from telegram.error import NetworkError, TimedOut, RetryAfter

# Application Components
from app.config import settings

from app.utils.logger import setup_logging, get_logger
from app.services.audio_processor import AudioProcessor
from app.services.elevenlabs_client import ElevenLabsClient
from app.services.openai_client import OpenAIClient

# Whitelist system
from app.whitelist import check_user_access, check_username_access
from app.bot_handlers import (
    admin_add_user_command,
    admin_remove_user_command,
    admin_add_username_command,
    admin_remove_username_command,
    admin_whitelist_status_command,
    admin_add_admin_command,
    admin_remove_admin_command,
)

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
            
            # Initialize audio processor (which includes ElevenLabs and OpenAI clients)
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
        
        # Test OpenAI
        try:
            health = await self.audio_processor.openai_client.check_api_health()
            if health.get("healthy"):
                logger.info("✅ OpenAI API: Healthy")
            else:
                logger.warning(f"⚠️ OpenAI API: {health.get('error', 'Unknown issue')}")
        except Exception as e:
            logger.warning(f"⚠️ OpenAI health check failed: {e}")
    
    def create_application(self) -> Application:
        """Create and configure the Telegram application"""
        logger.info("📱 Creating Telegram application...")
        
        # Create application with token
        application = Application.builder().token(settings.telegram_bot_token).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
        # Add admin whitelist command handlers
        # These commands use underscore format: /adduser_123456, /removeuser_123456, etc.
        application.add_handler(MessageHandler(
            filters.Regex(r'^/adduser_\d+') & filters.COMMAND, 
            admin_add_user_command
        ))
        application.add_handler(MessageHandler(
            filters.Regex(r'^/removeuser_\d+') & filters.COMMAND, 
            admin_remove_user_command
        ))
        application.add_handler(MessageHandler(
            filters.Regex(r'^/addusername_[\w@]+') & filters.COMMAND, 
            admin_add_username_command
        ))
        application.add_handler(MessageHandler(
            filters.Regex(r'^/removeusername_[\w@]+') & filters.COMMAND, 
            admin_remove_username_command
        ))
        # Admin management commands
        application.add_handler(MessageHandler(
            filters.Regex(r'^/addadmin_\d+') & filters.COMMAND, 
            admin_add_admin_command
        ))
        application.add_handler(MessageHandler(
            filters.Regex(r'^/removeadmin_\d+') & filters.COMMAND, 
            admin_remove_admin_command
        ))
        application.add_handler(CommandHandler("whitelist", admin_whitelist_status_command))
        
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
        
        # Check user access
        if not check_user_access(user.id):
            # Also check username access if user ID check fails
            username = user.username if user.username else ""
            if not check_username_access(username):
                logger.warning(f"Access denied for user {user.id} ({user.username})")
                await update.message.reply_text(
                    "❌ **Доступ запрещен**\n\n"
                    "Вы не авторизованы для использования этого бота.\n"
                    "Обратитесь к администратору для получения доступа."
                )
                return
        
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
            f"🎤 **Welcome to Audio Bot, {user.first_name}**\n\n"
        )
        
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        # Handle both edited messages and regular messages
        message = update.message or update.edited_message
        if not message:
            return
        
        user = update.effective_user
        
        # Check user access
        if not check_user_access(user.id):
            # Also check username access if user ID check fails
            username = user.username if user.username else ""
            if not check_username_access(username):
                logger.warning(f"Access denied for user {user.id} ({user.username}) attempting to use /help")
                await message.reply_text(
                    "❌ **Доступ запрещен**\n\n"
                    "Вы не авторизованы для использования этого бота.\n"
                    "Обратитесь к администратору для получения доступа."
                )
                return
            
        help_text = (
            "🤖 **Audio Bot Help**\n\n"
            "**Commands:**\n"
            "• `/start` - Start the bot and see welcome message\n"
            "• `/help` - Show this help message\n"
        )
        
        await message.reply_text(help_text, parse_mode="Markdown")
    
    
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
        
        # Check user access
        if not check_user_access(user.id):
            # Also check username access if user ID check fails
            username = user.username if user.username else ""
            if not check_username_access(username):
                logger.warning(f"Access denied for user {user.id} ({user.username}) attempting to process {audio_type}")
                await message.reply_text(
                    "❌ **Доступ запрещен**\n\n"
                    "Вы не авторизованы для использования этого бота.\n"
                    "Обратитесь к администратору для получения доступа."
                )
                return
        
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
                    "If the problem persists, try to connect the developer"
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
        
        # Enhanced grammar analysis and speaking tips
        grammar_issues = result.get("grammar_issues", [])
        speaking_tips = result.get("speaking_tips", [])
        confidence_score = result.get("confidence_score", 0)
        improvements_made = result.get("improvements_made", 0)
        method_used = result.get("method_used", "unknown")
        
        response += "\n"
        
        if grammar_issues and isinstance(grammar_issues, list) and len(grammar_issues) > 0:
            # Filter out placeholder messages
            real_issues = [issue for issue in grammar_issues if issue and "Unable to analyze" not in issue]
            if real_issues:
                response += f"🔍 **Grammar Analysis:**\n"
                for i, issue in enumerate(real_issues[:5], 1):  # Limit to 3 issues
                    response += f"• {issue}\n"
                response += "\n"
        
        if speaking_tips and isinstance(speaking_tips, list) and len(speaking_tips) > 0:
            # Filter out placeholder messages
            real_tips = [tip for tip in speaking_tips if tip and "Try speaking more clearly" not in tip]
            if real_tips:
                response += f"💡 **Speaking Improvement Tips:**\n"
                for i, tip in enumerate(real_tips[:5], 1):  # Limit to 3 tips
                    # Truncate long tips to keep response manageable
                    response += f"• {tip}\n"
                response += "\n"
        
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
        error = context.error
        
        # Handle network errors gracefully - these are transient and expected
        if isinstance(error, NetworkError):
            # Network errors are common and the library will retry automatically
            # Log at warning level instead of error to reduce noise
            logger.warning(
                f"⚠️ Network error (will retry automatically): {type(error).__name__}: {error}"
            )
            # Don't notify users about network errors - they're not user-facing issues
            return
        
        # Handle timeout errors similarly
        if isinstance(error, TimedOut):
            logger.warning(
                f"⏱️ Request timeout (will retry automatically): {error}"
            )
            return
        
        # Handle rate limiting - log but don't notify user
        if isinstance(error, RetryAfter):
            logger.warning(
                f"⏳ Rate limited by Telegram API. Retry after {error.retry_after} seconds"
            )
            return
        
        # For other errors, log as error and notify user if possible
        logger.error(
            f"❌ Exception while handling update {update}: {error}", 
            exc_info=error
        )
        
        # Try to notify the user if possible (only for non-network errors)
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
                # Sync whitelist config from Docker volume before shutdown
                await self._sync_whitelist_config()
                
                # Stop the application (this also stops the updater)
                await self.application.stop()
                await self.application.shutdown()
                
                self.is_running = False
                logger.info("✅ Bot stopped successfully")
                
            except Exception as e:
                logger.error(f"❌ Error stopping bot: {e}")
    
    async def _sync_whitelist_config(self):
        """Sync whitelist_config.py from Docker volume to project directory"""
        try:
            import os
            from pathlib import Path
            
            # Only sync if running in Docker
            docker_config = Path("/app/config/whitelist_config.py")
            if not docker_config.exists():
                logger.info("Not running in Docker, skipping config sync")
                return
            
            # Try to find project root (where whitelist_config.py should be)
            # This is tricky in Docker, so we'll use an environment variable or default
            project_root = os.getenv("PROJECT_ROOT", "/app")
            target_config = Path(project_root) / "whitelist_config.py"
            
            # If we can't write to project root, try to copy to a known location
            if not os.access(Path(project_root), os.W_OK):
                logger.warning("Cannot write to project root, config sync skipped")
                return
            
            # Copy from Docker volume to project directory
            import shutil
            if docker_config.exists():
                shutil.copy2(docker_config, target_config)
                logger.info(f"✅ Synced whitelist_config.py to {target_config}")
            else:
                logger.info("No config file in Docker volume to sync")
                
        except Exception as e:
            logger.warning(f"Could not sync whitelist config: {e}")
            # Don't fail shutdown if sync fails

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
        logger.info(f"  • OpenAI API: {'✅ Set' if settings.openai_api_key else '❌ Missing'}")
        logger.info(f"  • OpenAI Model: {settings.openai_model}")
        logger.info(f"  • Upload Dir: {settings.upload_dir}")
        logger.info(f"  • Log Level: {settings.log_level}")
        
        # Check for missing critical configuration
        if not all([settings.telegram_bot_token, settings.elevenlabs_api_key, settings.openai_api_key]):
            logger.error("❌ Missing required API keys! Check your .env file.")
            sys.exit(1)
        
        # Start the event loop
        asyncio.run(main())
        
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}", exc_info=True)
        sys.exit(1)
