"""
Database module for user management
====================================

Simple file-based database for tracking blocked users.
In a production environment, this could be replaced with a proper database.
"""
import json
import os
from pathlib import Path
from typing import Set
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Path to the blocked users database file
# Use writable location in Docker, fallback to current directory
def _get_db_file_path() -> Path:
    """Get the path to the database file, using writable location in Docker"""
    # Try writable locations first (Docker)
    writable_locations = [
        Path("/app/uploads/blocked_users.json"),  # Uploads directory (mounted volume)
        Path("/app/logs/blocked_users.json"),     # Logs directory (mounted volume)
        Path("/app/data/blocked_users.json"),     # Data directory (if exists)
    ]
    
    for db_path in writable_locations:
        if db_path.parent.exists():
            try:
                # Check if we can write to this location
                import os
                if os.access(db_path.parent, os.W_OK):
                    # Create parent directory if needed
                    db_path.parent.mkdir(parents=True, exist_ok=True)
                    return db_path
            except Exception:
                continue
    
    # Fallback to current directory
    return Path("blocked_users.json")

DB_FILE = _get_db_file_path()


class UserDatabase:
    """Simple file-based database for user management"""
    
    def __init__(self, db_file: Path = None):
        # Use default path if not provided
        if db_file is None:
            db_file = _get_db_file_path()
        self.db_file = db_file
        self.blocked_users: Set[int] = set()
        logger.info(f"Using database file: {self.db_file}")
        self._load_database()
    
    def _load_database(self):
        """Load blocked users from file"""
        try:
            if self.db_file.exists():
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.blocked_users = set(data.get('blocked_users', []))
                logger.info(f"Loaded {len(self.blocked_users)} blocked users from database")
            else:
                self.blocked_users = set()
                self._save_database()
                logger.info("Created new blocked users database")
        except Exception as e:
            logger.error(f"Error loading database: {e}")
            self.blocked_users = set()
    
    def _save_database(self):
        """Save blocked users to file"""
        try:
            data = {
                'blocked_users': list(self.blocked_users)
            }
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving database: {e}")
    
    def is_user_blocked(self, user_id: int) -> bool:
        """Check if a user is blocked"""
        return user_id in self.blocked_users
    
    def block_user(self, user_id: int) -> bool:
        """Block a user"""
        try:
            self.blocked_users.add(user_id)
            self._save_database()
            logger.info(f"User {user_id} has been blocked")
            return True
        except Exception as e:
            logger.error(f"Error blocking user {user_id}: {e}")
            return False
    
    def unblock_user(self, user_id: int) -> bool:
        """Unblock a user"""
        try:
            if user_id in self.blocked_users:
                self.blocked_users.remove(user_id)
                self._save_database()
                logger.info(f"User {user_id} has been unblocked")
                return True
            return False
        except Exception as e:
            logger.error(f"Error unblocking user {user_id}: {e}")
            return False
    
    def add_user(self, user_id: int) -> bool:
        """Add a user to the database (for tracking purposes)"""
        # This is a placeholder for future functionality
        # Currently just ensures the user is not blocked
        return self.unblock_user(user_id)


# Global database instance
db = UserDatabase()

