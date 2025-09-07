"""
Configuration management for Telegram Audio Bot
"""
import os
from pathlib import Path
from typing import Optional


class Settings:
    """Application settings loaded from environment variables"""
    
    def __init__(self):
        # Required API Keys
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        
        # Optional Configuration with defaults
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "26214400"))  # 25MB in bytes
        self.upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
        self.elevenlabs_model: str = os.getenv("ELEVEN_LABS_MODEL", "scribe_v1")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        self.polling_interval: float = float(os.getenv("POLLING_INTERVAL", "1.0"))
        
        # FastAPI/Web server settings
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        
        # Ensure upload directory exists
        self._ensure_upload_dir()
    
    def _ensure_upload_dir(self):
        """Create upload directory if it doesn't exist"""
        upload_path = Path(self.upload_dir)
        upload_path.mkdir(parents=True, exist_ok=True)
    
    def validate_required_settings(self) -> bool:
        """Validate that all required settings are present"""
        required_settings = [
            self.telegram_bot_token,
            self.elevenlabs_api_key,
            self.gemini_api_key
        ]
        return all(setting and setting.strip() for setting in required_settings)
    
    def get_masked_api_keys(self) -> dict:
        """Get API keys with sensitive parts masked for logging"""
        def mask_key(key: str) -> str:
            if not key or len(key) < 8:
                return "***"
            return f"{'*' * 10}...{key[-4:]}"
        
        return {
            "telegram_bot_token": mask_key(self.telegram_bot_token),
            "elevenlabs_api_key": mask_key(self.elevenlabs_api_key),
            "gemini_api_key": mask_key(self.gemini_api_key)
        }
    
    def __repr__(self) -> str:
        """String representation with masked sensitive data"""
        masked_keys = self.get_masked_api_keys()
        return (
            f"Settings("
            f"telegram_bot_token='{masked_keys['telegram_bot_token']}', "
            f"elevenlabs_api_key='{masked_keys['elevenlabs_api_key']}', "
            f"gemini_api_key='{masked_keys['gemini_api_key']}', "
            f"log_level='{self.log_level}', "
            f"max_file_size={self.max_file_size}, "
            f"upload_dir='{self.upload_dir}', "
            f"elevenlabs_model='{self.elevenlabs_model}', "
            f"gemini_model='{self.gemini_model}', "
            f"polling_interval={self.polling_interval}, "
            f"host='{self.host}', "
            f"port={self.port}"
            f")"
        )


# Global settings instance
settings = Settings()