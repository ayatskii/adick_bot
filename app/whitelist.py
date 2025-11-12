"""
Whitelist Management Module
============================

This module provides functions for managing the whitelist system,
including permanent modifications to the configuration file.
"""
import re
import os
import shutil
from pathlib import Path
from typing import List
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Import whitelist config
# Try writable location first, then original location
config = None
try:
    # Try writable config location first (Docker volume)
    import sys
    writable_config_path = Path("/app/config")
    if writable_config_path.exists():
        sys.path.insert(0, str(writable_config_path))
        try:
            import whitelist_config as config
            logger.info("Loaded whitelist_config from writable location: /app/config")
        except ImportError:
            pass
    
    # Fallback to original location
    if config is None:
        import whitelist_config as config
        logger.info("Loaded whitelist_config from original location")
except ImportError:
    logger.error("Failed to import whitelist_config. Make sure whitelist_config.py exists.")
    config = None

# Import database
from app.db import db


def is_admin(user_id: int) -> bool:
    """Check if a user is an admin"""
    if not config or not hasattr(config, 'ADMIN_USER_IDS'):
        return False
    return user_id in config.ADMIN_USER_IDS


def check_user_access(user_id: int) -> bool:
    """Check if user has access to the bot"""
    # If user is blocked, deny access
    if db.is_user_blocked(user_id):
        return False
    
    # Admins always have access (even if not in whitelist)
    if is_admin(user_id):
        return True
    
    # If whitelist is enabled, check if user is authorized
    if config and hasattr(config, 'ENABLE_WHITELIST') and config.ENABLE_WHITELIST:
        if hasattr(config, 'AUTHORIZED_USER_IDS'):
            return user_id in config.AUTHORIZED_USER_IDS
    
    # If whitelist is disabled, allow all non-blocked users
    return True


def check_username_access(username: str) -> bool:
    """Check if username has access to the bot"""
    if not username or not config:
        return False
    
    if not hasattr(config, 'ENABLE_WHITELIST') or not config.ENABLE_WHITELIST:
        return False
    
    if not hasattr(config, 'AUTHORIZED_USERNAMES'):
        return False
    
    return username.lower() in [u.lower() for u in config.AUTHORIZED_USERNAMES]


def _get_config_file_path() -> Path:
    """Get the path to the whitelist_config.py file"""
    # In Docker, use writable config directory first (mounted volume)
    writable_config = Path("/app/config/whitelist_config.py")
    if writable_config.exists() and os.access(writable_config.parent, os.W_OK):
        logger.info(f"Using writable config location: {writable_config}")
        return writable_config
    
    # Try to find the config file in the project root
    current_dir = Path(__file__).parent.parent
    config_file = current_dir / "whitelist_config.py"
    
    logger.info(f"Checking config file at: {config_file} (exists: {config_file.exists()})")
    
    if config_file.exists():
        # Check if we can write to it
        can_write = os.access(config_file, os.W_OK)
        logger.info(f"Config file writable: {can_write}")
        
        # If original exists but is read-only, try to copy to writable location (Docker only)
        if not can_write:
            # Try to copy to writable location (Docker)
            writable_dir = Path("/app/config")
            if writable_dir.exists() and os.access(writable_dir, os.W_OK):
                import shutil
                writable_config = writable_dir / "whitelist_config.py"
                shutil.copy2(config_file, writable_config)
                logger.info(f"Copied whitelist_config.py to writable location: {writable_config}")
                return writable_config
            else:
                logger.warning(f"Cannot write to config file and no writable location available: {config_file}")
        else:
            # File exists and is writable - use it
            logger.info(f"Using config file: {config_file}")
            return config_file
    
    # If file doesn't exist, try current directory
    current_dir_config = Path("whitelist_config.py")
    if current_dir_config.exists():
        logger.info(f"Using config file from current directory: {current_dir_config}")
        return current_dir_config
    
    # Last resort: return the expected location in project root
    logger.warning(f"Config file not found, will use: {config_file}")
    return config_file


def _sync_to_project_directory(source_file: Path):
    """
    Sync whitelist_config.py from Docker volume to project directory
    This allows the file to be updated in the project directory even when running in Docker
    """
    try:
        # Only sync if source is in Docker volume location
        if str(source_file) != "/app/config/whitelist_config.py":
            return  # Not in Docker, no need to sync
        
        # Try to copy to project root if it's writable (bind mount scenario)
        project_root_config = Path("/app/whitelist_config.py")
        if project_root_config.parent.exists() and os.access(project_root_config.parent, os.W_OK):
            try:
                shutil.copy2(source_file, project_root_config)
                logger.info(f"✅ Synced config to project directory: {project_root_config}")
                return
            except Exception as e:
                logger.debug(f"Could not sync to project root: {e}")
        
        # If direct copy doesn't work, log that sync should happen on shutdown
        logger.info("📝 Config updated in Docker volume: /app/config/whitelist_config.py")
        logger.info("   To sync to project directory, run: make sync-config")
        logger.info("   Or wait for automatic sync on Docker shutdown")
        
    except Exception as e:
        logger.warning(f"Could not sync config to project directory: {e}")


def _reload_config():
    """Reload the whitelist configuration module"""
    global config
    try:
        import importlib
        import sys
        
        logger.info("🔄 Reloading whitelist configuration...")
        
        # Remove old config from sys.modules if it exists
        # Need to remove all variations that might be cached
        modules_to_remove = []
        for key in list(sys.modules.keys()):
            if key == 'whitelist_config' or key.endswith('.whitelist_config'):
                modules_to_remove.append(key)
        
        for mod in modules_to_remove:
            del sys.modules[mod]
            logger.debug(f"Removed cached module: {mod}")
        
        # Reset config to None to force fresh import
        config = None
        
        # Try to reload from writable location first (Docker)
        writable_config_path = Path("/app/config")
        if writable_config_path.exists():
            # Remove old path if it exists
            if str(writable_config_path) in sys.path:
                sys.path.remove(str(writable_config_path))
            sys.path.insert(0, str(writable_config_path))
            try:
                import whitelist_config
                config = whitelist_config
                logger.info("✅ Reloaded whitelist_config from writable location: /app/config")
                logger.info(f"   Loaded {len(getattr(config, 'AUTHORIZED_USER_IDS', []))} user IDs")
                logger.info(f"   Loaded {len(getattr(config, 'AUTHORIZED_USERNAMES', []))} usernames")
                return
            except ImportError as e:
                logger.warning(f"Could not import from writable location: {e}")
        
        # Fallback to original location
        # Remove writable path from sys.path if it's there
        if str(writable_config_path) in sys.path:
            sys.path.remove(str(writable_config_path))
        
        try:
            import whitelist_config
            config = whitelist_config
            logger.info("✅ Reloaded whitelist_config from original location")
            logger.info(f"   Loaded {len(getattr(config, 'AUTHORIZED_USER_IDS', []))} user IDs")
            logger.info(f"   Loaded {len(getattr(config, 'AUTHORIZED_USERNAMES', []))} usernames")
        except ImportError as e:
            logger.error(f"❌ Failed to import whitelist_config: {e}")
            config = None
        
    except Exception as e:
        logger.error(f"❌ Error reloading config: {e}", exc_info=True)


def add_user_to_permanent_whitelist(user_id: int) -> bool:
    """
    Permanently adds a user ID to the whitelist by modifying whitelist_config.py
    
    Args:
        user_id: The Telegram user ID to add
        
    Returns:
        True if successful, False otherwise
    """
    try:
        config_file = _get_config_file_path()
        
        logger.info(f"Attempting to add user {user_id} to whitelist config at: {config_file}")
        logger.info(f"Config file absolute path: {config_file.absolute()}")
        logger.info(f"Config file exists: {config_file.exists()}")
        
        if not config_file.exists():
            logger.error(f"Config file not found: {config_file}")
            logger.error(f"Current working directory: {os.getcwd()}")
            logger.error(f"Config file absolute path: {config_file.absolute()}")
            return False
        
        # Check if we can write to the file
        if not os.access(config_file, os.W_OK):
            logger.error(f"Cannot write to config file: {config_file}")
            try:
                logger.error(f"File permissions: {oct(config_file.stat().st_mode)}")
            except:
                pass
            return False
        
        # Read current config file
        logger.info(f"Reading config file: {config_file}")
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if user ID already exists
        if f"{user_id}," in content or f"{user_id}]" in content:
            logger.info(f"User ID {user_id} already in whitelist")
            return True
        
        # Find the AUTHORIZED_USER_IDS section using regex
        pattern = r'(AUTHORIZED_USER_IDS\s*=\s*\[)(.*?)(\])'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.error("Could not find AUTHORIZED_USER_IDS section in config file")
            return False
        
        # Get the list content
        list_content = match.group(2)
        
        # Add the new user ID before the closing bracket
        # Find the last entry and add after it
        lines = list_content.strip().split('\n')
        if lines and lines[-1].strip():
            # Add comma and new entry
            new_entry = f"    {user_id},"
            # Insert before the closing bracket
            replacement = match.group(1) + list_content + '\n' + new_entry + '\n' + match.group(3)
        else:
            # Empty list, add first entry
            new_entry = f"    {user_id},"
            replacement = match.group(1) + '\n' + new_entry + '\n' + match.group(3)
        
        # Replace in content
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        # Write back to file
        logger.info(f"Writing updated config to: {config_file}")
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            logger.info(f"Successfully wrote to config file: {config_file}")
        except Exception as write_error:
            logger.error(f"Failed to write to config file: {write_error}", exc_info=True)
            return False
        
        # Verify the write was successful
        if not config_file.exists():
            logger.error(f"Config file disappeared after write: {config_file}")
            return False
        
        # Update runtime configuration
        _reload_config()
        
        # Also update the runtime config object
        if config and hasattr(config, 'AUTHORIZED_USER_IDS'):
            if user_id not in config.AUTHORIZED_USER_IDS:
                config.AUTHORIZED_USER_IDS.append(user_id)
        
        # Sync to project directory if running in Docker
        _sync_to_project_directory(config_file)
        
        logger.info(f"User ID {user_id} successfully added to permanent whitelist at {config_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding user {user_id} to permanent whitelist: {e}", exc_info=True)
        return False


def remove_user_from_permanent_whitelist(user_id: int) -> bool:
    """
    Permanently removes a user ID from the whitelist by modifying whitelist_config.py
    
    Args:
        user_id: The Telegram user ID to remove
        
    Returns:
        True if successful, False otherwise
    """
    try:
        config_file = _get_config_file_path()
        
        if not config_file.exists():
            logger.error(f"Config file not found: {config_file}")
            return False
        
        # Read current config file
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use regex to find and remove the user ID
        # Pattern matches: optional whitespace, user_id, optional comma, optional whitespace
        pattern = rf'(\s*){re.escape(str(user_id))}(\s*,?\s*)'
        
        # Remove the user ID line
        new_content = re.sub(pattern, '', content)
        
        # Clean up any double newlines that might have been created
        new_content = re.sub(r'\n\n\n+', '\n\n', new_content)
        
        # Write back to file
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Update runtime configuration
        _reload_config()
        
        # Also update the runtime config object
        if config and hasattr(config, 'AUTHORIZED_USER_IDS'):
            if user_id in config.AUTHORIZED_USER_IDS:
                config.AUTHORIZED_USER_IDS.remove(user_id)
        
        # Sync to project directory if running in Docker
        _sync_to_project_directory(config_file)
        
        logger.info(f"User ID {user_id} removed from permanent whitelist")
        return True
        
    except Exception as e:
        logger.error(f"Error removing user {user_id} from permanent whitelist: {e}", exc_info=True)
        return False


def add_username_to_permanent_whitelist(username: str) -> bool:
    """
    Permanently adds a username to the whitelist by modifying whitelist_config.py
    
    Args:
        username: The Telegram username to add (without @ symbol)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Remove @ symbol if present
        username = username.lstrip('@')
        
        if not username:
            logger.error("Username cannot be empty")
            return False
        
        config_file = _get_config_file_path()
        
        if not config_file.exists():
            logger.error(f"Config file not found: {config_file}")
            return False
        
        # Read current config file
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if username already exists (case-insensitive)
        username_lower = username.lower()
        pattern_check = rf'["\']([^"\']+)["\']'
        existing_usernames = re.findall(pattern_check, content)
        if any(u.lower() == username_lower for u in existing_usernames):
            logger.info(f"Username {username} already in whitelist")
            return True
        
        # Find the AUTHORIZED_USERNAMES section using regex
        pattern = r'(AUTHORIZED_USERNAMES\s*=\s*\[)(.*?)(\])'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.error("Could not find AUTHORIZED_USERNAMES section in config file")
            return False
        
        # Get the list content
        list_content = match.group(2)
        
        # Add the new username with proper string formatting
        new_entry = f'    "{username}",'
        
        # Check if list is empty (only comments)
        if not list_content.strip() or list_content.strip().startswith('#'):
            # Empty list, add first entry
            replacement = match.group(1) + '\n' + new_entry + '\n' + match.group(3)
        else:
            # Add after existing entries
            replacement = match.group(1) + list_content + '\n' + new_entry + '\n' + match.group(3)
        
        # Replace in content
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        # Write back to file
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Update runtime configuration
        _reload_config()
        
        # Also update the runtime config object
        if config and hasattr(config, 'AUTHORIZED_USERNAMES'):
            if username not in config.AUTHORIZED_USERNAMES:
                config.AUTHORIZED_USERNAMES.append(username)
        
        # Sync to project directory if running in Docker
        _sync_to_project_directory(config_file)
        
        logger.info(f"Username {username} added to permanent whitelist at {config_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding username {username} to permanent whitelist: {e}", exc_info=True)
        return False


def remove_username_from_permanent_whitelist(username: str) -> bool:
    """
    Permanently removes a username from the whitelist by modifying whitelist_config.py
    
    Args:
        username: The Telegram username to remove (without @ symbol)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Remove @ symbol if present
        username = username.lstrip('@')
        
        if not username:
            logger.error("Username cannot be empty")
            return False
        
        config_file = _get_config_file_path()
        
        if not config_file.exists():
            logger.error(f"Config file not found: {config_file}")
            return False
        
        # Read current config file
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use regex to find and remove the username (case-insensitive)
        # Pattern matches: optional whitespace, quoted username, optional comma
        # We need to match the exact username in quotes
        pattern = rf'(\s*)["\']{re.escape(username)}["\'](\s*,?\s*)'
        
        # Remove the username line
        new_content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Clean up any double newlines that might have been created
        new_content = re.sub(r'\n\n\n+', '\n\n', new_content)
        
        # Write back to file
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Update runtime configuration
        _reload_config()
        
        # Also update the runtime config object
        if config and hasattr(config, 'AUTHORIZED_USERNAMES'):
            # Remove case-insensitively
            username_lower = username.lower()
            config.AUTHORIZED_USERNAMES = [
                u for u in config.AUTHORIZED_USERNAMES 
                if u.lower() != username_lower
            ]
        
        # Sync to project directory if running in Docker
        _sync_to_project_directory(config_file)
        
        logger.info(f"Username {username} removed from permanent whitelist")
        return True
        
    except Exception as e:
        logger.error(f"Error removing username {username} from permanent whitelist: {e}", exc_info=True)
        return False


def add_admin_to_permanent_config(user_id: int) -> bool:
    """
    Permanently adds a user ID to the admin list by modifying whitelist_config.py
    
    Args:
        user_id: The Telegram user ID to add as admin
        
    Returns:
        True if successful, False otherwise
    """
    try:
        config_file = _get_config_file_path()
        
        logger.info(f"Attempting to add admin {user_id} to config at: {config_file}")
        logger.info(f"Config file absolute path: {config_file.absolute()}")
        logger.info(f"Config file exists: {config_file.exists()}")
        
        if not config_file.exists():
            logger.error(f"Config file not found: {config_file}")
            return False
        
        # Check if we can write to the file
        if not os.access(config_file, os.W_OK):
            logger.error(f"Cannot write to config file: {config_file}")
            try:
                logger.error(f"File permissions: {oct(config_file.stat().st_mode)}")
            except:
                pass
            return False
        
        # Read current config file
        logger.info(f"Reading config file: {config_file}")
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # First, check if user ID already exists in ADMIN_USER_IDS section specifically
        admin_pattern = r'ADMIN_USER_IDS\s*=\s*\[(.*?)\]'
        admin_match = re.search(admin_pattern, content, re.DOTALL)
        
        if admin_match:
            admin_content = admin_match.group(1)
            # Check if user ID is already in the admin list
            # Use word boundary to avoid partial matches
            user_id_pattern = rf'\b{re.escape(str(user_id))}\b'
            if re.search(user_id_pattern, admin_content):
                logger.info(f"User ID {user_id} already in admin list")
                return True
        
        # Find the ADMIN_USER_IDS section using regex
        pattern = r'(ADMIN_USER_IDS\s*=\s*\[)(.*?)(\])'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            logger.error("Could not find ADMIN_USER_IDS section in config file")
            return False
        
        # Get the list content
        list_content = match.group(2)
        
        # Add the new admin ID
        # Strip the list content to check if it's empty (ignoring whitespace and comments)
        stripped_content = list_content.strip()
        # Remove comments and empty lines for checking
        non_comment_lines = [line for line in stripped_content.split('\n') 
                           if line.strip() and not line.strip().startswith('#')]
        
        if non_comment_lines:
            # List has entries, add new entry after the last one
            # Ensure the last existing entry has a comma
            lines = list_content.rstrip().split('\n')
            # Find the last non-empty, non-comment line
            last_line_idx = -1
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if line and not line.startswith('#'):
                    last_line_idx = i
                    break
            
            if last_line_idx >= 0:
                # Ensure the last line has a comma
                last_line = lines[last_line_idx]
                if not last_line.rstrip().endswith(','):
                    # Add comma to the last line if it doesn't have one
                    lines[last_line_idx] = last_line.rstrip() + ','
            
            # Reconstruct list_content with proper formatting
            formatted_content = '\n'.join(lines)
            if not formatted_content.endswith('\n'):
                formatted_content += '\n'
            
            # Add the new entry
            new_entry = f"    {user_id},"
            replacement = match.group(1) + formatted_content + new_entry + '\n' + match.group(3)
        else:
            # Empty list, add first entry
            new_entry = f"    {user_id},"
            replacement = match.group(1) + '\n' + new_entry + '\n' + match.group(3)
        
        # Replace in content
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        # Write back to file
        logger.info(f"Writing updated config to: {config_file}")
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            logger.info(f"Successfully wrote to config file: {config_file}")
        except Exception as write_error:
            logger.error(f"Failed to write to config file: {write_error}", exc_info=True)
            return False
        
        # Verify the write was successful
        if not config_file.exists():
            logger.error(f"Config file disappeared after write: {config_file}")
            return False
        
        # Update runtime configuration
        _reload_config()
        
        # Also update the runtime config object
        if config and hasattr(config, 'ADMIN_USER_IDS'):
            if user_id not in config.ADMIN_USER_IDS:
                config.ADMIN_USER_IDS.append(user_id)
        
        # Sync to project directory if running in Docker
        _sync_to_project_directory(config_file)
        
        logger.info(f"User ID {user_id} successfully added to admin list at {config_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding admin {user_id}: {e}", exc_info=True)
        return False


def remove_admin_from_permanent_config(user_id: int) -> bool:
    """
    Permanently removes a user ID from the admin list by modifying whitelist_config.py
    
    Args:
        user_id: The Telegram user ID to remove from admin list
        
    Returns:
        True if successful, False otherwise
    """
    try:
        config_file = _get_config_file_path()
        
        if not config_file.exists():
            logger.error(f"Config file not found: {config_file}")
            return False
        
        # Read current config file
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use regex to find and remove the admin ID from ADMIN_USER_IDS section only
        # First, find the ADMIN_USER_IDS section
        admin_pattern = r'(ADMIN_USER_IDS\s*=\s*\[)(.*?)(\])'
        admin_match = re.search(admin_pattern, content, re.DOTALL)
        
        if not admin_match:
            logger.error("Could not find ADMIN_USER_IDS section in config file")
            return False
        
        # Check if user ID is in admin list
        admin_content = admin_match.group(2)
        if str(user_id) not in admin_content:
            logger.info(f"User ID {user_id} not in admin list")
            return True
        
        # Remove the user ID from admin section
        user_id_pattern = rf'(\s*){re.escape(str(user_id))}(\s*,?\s*)'
        new_admin_content = re.sub(user_id_pattern, '', admin_content)
        
        # Reconstruct the section
        replacement = admin_match.group(1) + new_admin_content + admin_match.group(3)
        new_content = re.sub(admin_pattern, replacement, content, flags=re.DOTALL)
        
        # Clean up any double newlines
        new_content = re.sub(r'\n\n\n+', '\n\n', new_content)
        
        # Write back to file
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Update runtime configuration
        _reload_config()
        
        # Also update the runtime config object
        if config and hasattr(config, 'ADMIN_USER_IDS'):
            if user_id in config.ADMIN_USER_IDS:
                config.ADMIN_USER_IDS.remove(user_id)
        
        # Sync to project directory if running in Docker
        _sync_to_project_directory(config_file)
        
        logger.info(f"User ID {user_id} removed from admin list")
        return True
        
    except Exception as e:
        logger.error(f"Error removing admin {user_id}: {e}", exc_info=True)
        return False
