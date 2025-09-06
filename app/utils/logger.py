"""
Advanced logging configuration for the Telegram Audio Bot
"""
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from pythonjsonlogger import jsonlogger
from app.config import settings

def setup_logging():
    """
    Configure comprehensive logging for the application
    
    This function sets up different logging behaviors for development vs production:
    - Development: Human-readable console output with colors and detailed formatting
    - Production: Structured JSON logging for log aggregation systems
    """
    
    # ===========================================
    # 1. INITIALIZE ROOT LOGGER
    # ===========================================
    
    # Get the root logger (parent of all other loggers)
    root_logger = logging.getLogger()
    
    # Set the minimum logging level based on configuration
    if settings.log_level == "DEBUG":
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # ===========================================
    # 2. CLEAN EXISTING HANDLERS
    # ===========================================
    
    # Remove any existing handlers to prevent duplicate logging
    # This is important when reloading the module or running tests
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # ===========================================
    # 3. SETUP CONSOLE HANDLER
    # ===========================================
    
    # Create handler that outputs to console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(root_logger.level)
    
    # ===========================================
    # 4. CHOOSE FORMATTER BASED ON ENVIRONMENT
    # ===========================================
    
    if settings.log_level == "DEBUG":
        # DEVELOPMENT FORMATTER
        # Human-readable format with timestamp, logger name, level, and message
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # PRODUCTION FORMATTER
        # JSON structured logging for parsing by log aggregation systems
        # (ELK Stack, Fluentd, CloudWatch, etc.)
        formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
    
    # Apply formatter to handler
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # ===========================================
    # 5. OPTIONAL: FILE LOGGING
    # ===========================================
    
    # Add file logging for production environments
    if settings.log_level != "DEBUG":
        setup_file_logging(root_logger, formatter)
    
    # ===========================================
    # 6. CONFIGURE THIRD-PARTY LIBRARY LOGGERS
    # ===========================================
    
    # Reduce noise from verbose third-party libraries
    # These libraries log too much information at INFO level
    noisy_loggers = [
        "httpx",           # HTTP client library
        "httpcore",        # HTTP core library  
        "telegram",        # python-telegram-bot library
        "urllib3",         # HTTP library used by requests
        "asyncio",         # Async framework (very verbose)
        "aiofiles",        # Async file operations
        "multipart",       # File upload handling
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # ===========================================
    # 7. LOG STARTUP MESSAGE
    # ===========================================
    
    startup_logger = logging.getLogger("startup")
    startup_logger.info("Logging system configured successfully")
    startup_logger.info(f"Log level: {settings.log_level}")
    startup_logger.info(f"Upload directory: {settings.upload_dir}")

def setup_file_logging(root_logger, formatter):
    """
    Configure file-based logging for production environments
    
    Args:
        root_logger: The root logger instance
        formatter: The formatter to use for file output
    """
    try:
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create rotating file handler
        from logging.handlers import RotatingFileHandler
        
        # Log file with automatic rotation (10MB max, keep 5 files)
        file_handler = RotatingFileHandler(
            filename=log_dir / "bot.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        
        root_logger.addHandler(file_handler)
        
        logging.getLogger("startup").info("File logging configured")
        
    except Exception as e:
        # Don't crash if file logging fails
        logging.getLogger("startup").warning(f"File logging setup failed: {e}")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name
    
    This is a convenience function to get loggers with consistent naming.
    
    Args:
        name: Name of the logger (usually __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        logger = get_logger(__name__)
        logger.info("This is an info message")
    """
    return logging.getLogger(name)

def log_function_call(func):
    """
    Decorator to log function calls (useful for debugging)
    
    Usage:
        @log_function_call
        def my_function(arg1, arg2):
            return "result"
    """
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned: {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
            raise
    
    return wrapper

# Initialize logging when module is imported
if not logging.getLogger().handlers:
    setup_logging()
