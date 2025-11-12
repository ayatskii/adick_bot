"""
Bot Handlers for Whitelist Management
======================================

This module contains all admin command handlers for managing the whitelist system.
"""
from telegram import Update
from telegram.ext import ContextTypes
from app.whitelist import (
    check_user_access,
    check_username_access,
    is_admin,
    add_user_to_permanent_whitelist,
    remove_user_from_permanent_whitelist,
    add_username_to_permanent_whitelist,
    remove_username_from_permanent_whitelist,
    add_admin_to_permanent_config,
    remove_admin_from_permanent_config,
)
from app.db import db
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Config is accessed dynamically from app.whitelist module
# This ensures we always get the latest config after reloads


def require_admin(func):
    """Decorator to require admin access for a command"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not is_admin(user_id):
            await update.message.reply_text(
                "❌ У вас нет прав администратора для выполнения этой команды."
            )
            logger.warning(f"Non-admin user {user_id} attempted to use admin command")
            return
        
        return await func(update, context)
    
    return wrapper


@require_admin
async def admin_add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to permanently add a user to whitelist
    Command: /adduser_<user_id>
    """
    try:
        user_id = update.effective_user.id
        command_text = update.message.text
        
        # Extract user ID from command
        if '_' not in command_text:
            await update.message.reply_text(
                "❌ Неверный формат команды. Используйте: /adduser_123456789"
            )
            return
        
        try:
            target_user_id = int(command_text.split('_')[1])
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Неверный формат ID пользователя. Используйте: /adduser_123456789"
            )
            return
        
        # Check if user is already in whitelist (get fresh config)
        from app import whitelist
        current_config = whitelist.config
        if current_config and hasattr(current_config, 'AUTHORIZED_USER_IDS'):
            if target_user_id in current_config.AUTHORIZED_USER_IDS:
                await update.message.reply_text(
                    f"ℹ️ Пользователь {target_user_id} уже находится в whitelist."
                )
                return
        
        # Add user to permanent whitelist
        success = add_user_to_permanent_whitelist(target_user_id)
        
        if success:
            # Also add to database (for tracking)
            db.add_user(target_user_id)
            
            await update.message.reply_text(
                f"✅ Пользователь {target_user_id} добавлен в постоянный whitelist!\n\n"
                f"🔄 Пользователь теперь имеет постоянный доступ к боту.\n"
                f"📝 ID пользователя добавлен в whitelist_config.py и сохранится после перезапуска бота."
            )
            logger.info(f"Admin {user_id} added user {target_user_id} to permanent whitelist")
        else:
            await update.message.reply_text(
                f"❌ Ошибка при добавлении пользователя {target_user_id} в whitelist."
            )
            logger.error(f"Failed to add user {target_user_id} to whitelist")
            
    except Exception as e:
        logger.error(f"Error in admin_add_user_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")


@require_admin
async def admin_remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to permanently remove a user from whitelist
    Command: /removeuser_<user_id>
    """
    try:
        user_id = update.effective_user.id
        command_text = update.message.text
        
        # Extract user ID from command
        if '_' not in command_text:
            await update.message.reply_text(
                "❌ Неверный формат команды. Используйте: /removeuser_123456789"
            )
            return
        
        try:
            target_user_id = int(command_text.split('_')[1])
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Неверный формат ID пользователя. Используйте: /removeuser_123456789"
            )
            return
        
        # Prevent self-removal for admins
        if is_admin(target_user_id):
            await update.message.reply_text(
                "❌ Нельзя удалить администратора из whitelist."
            )
            return
        
        # Check if user is in whitelist (get fresh config)
        from app import whitelist
        current_config = whitelist.config
        if current_config and hasattr(current_config, 'AUTHORIZED_USER_IDS'):
            if target_user_id not in current_config.AUTHORIZED_USER_IDS:
                await update.message.reply_text(
                    f"ℹ️ Пользователь {target_user_id} не находится в whitelist."
                )
                return
        
        # Remove user from permanent whitelist
        success = remove_user_from_permanent_whitelist(target_user_id)
        
        if success:
            await update.message.reply_text(
                f"✅ Пользователь {target_user_id} удален из постоянного whitelist.\n\n"
                f"🔄 Изменения сохранены в whitelist_config.py."
            )
            logger.info(f"Admin {user_id} removed user {target_user_id} from permanent whitelist")
        else:
            await update.message.reply_text(
                f"❌ Ошибка при удалении пользователя {target_user_id} из whitelist."
            )
            logger.error(f"Failed to remove user {target_user_id} from whitelist")
            
    except Exception as e:
        logger.error(f"Error in admin_remove_user_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")


@require_admin
async def admin_add_username_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to permanently add a username to whitelist
    Command: /addusername_<username>
    """
    try:
        user_id = update.effective_user.id
        command_text = update.message.text
        
        # Extract username from command
        if '_' not in command_text:
            await update.message.reply_text(
                "❌ Неверный формат команды. Используйте: /addusername_johndoe"
            )
            return
        
        username = command_text.split('_', 1)[1].strip()
        
        # Remove @ symbol if present
        username = username.lstrip('@')
        
        if not username:
            await update.message.reply_text(
                "❌ Username не может быть пустым."
            )
            return
        
        # Check if username already exists (case-insensitive) - get fresh config
        from app import whitelist
        current_config = whitelist.config
        if current_config and hasattr(current_config, 'AUTHORIZED_USERNAMES'):
            username_lower = username.lower()
            if any(u.lower() == username_lower for u in current_config.AUTHORIZED_USERNAMES):
                await update.message.reply_text(
                    f"ℹ️ Username @{username} уже находится в whitelist."
                )
                return
        
        # Add username to permanent whitelist
        success = add_username_to_permanent_whitelist(username)
        
        if success:
            await update.message.reply_text(
                f"✅ Username @{username} добавлен в постоянный whitelist!\n\n"
                f"🔄 Username добавлен в whitelist_config.py и сохранится после перезапуска бота."
            )
            logger.info(f"Admin {user_id} added username {username} to permanent whitelist")
        else:
            await update.message.reply_text(
                f"❌ Ошибка при добавлении username @{username} в whitelist."
            )
            logger.error(f"Failed to add username {username} to whitelist")
            
    except Exception as e:
        logger.error(f"Error in admin_add_username_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")


@require_admin
async def admin_remove_username_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to permanently remove a username from whitelist
    Command: /removeusername_<username>
    """
    try:
        user_id = update.effective_user.id
        command_text = update.message.text
        
        # Extract username from command
        if '_' not in command_text:
            await update.message.reply_text(
                "❌ Неверный формат команды. Используйте: /removeusername_johndoe"
            )
            return
        
        username = command_text.split('_', 1)[1].strip()
        
        # Remove @ symbol if present
        username = username.lstrip('@')
        
        if not username:
            await update.message.reply_text(
                "❌ Username не может быть пустым."
            )
            return
        
        # Check if username exists (case-insensitive) - get fresh config
        from app import whitelist
        current_config = whitelist.config
        if current_config and hasattr(current_config, 'AUTHORIZED_USERNAMES'):
            username_lower = username.lower()
            if not any(u.lower() == username_lower for u in current_config.AUTHORIZED_USERNAMES):
                await update.message.reply_text(
                    f"ℹ️ Username @{username} не находится в whitelist."
                )
                return
        
        # Remove username from permanent whitelist
        success = remove_username_from_permanent_whitelist(username)
        
        if success:
            await update.message.reply_text(
                f"✅ Username @{username} удален из постоянного whitelist.\n\n"
                f"🔄 Изменения сохранены в whitelist_config.py."
            )
            logger.info(f"Admin {user_id} removed username {username} from permanent whitelist")
        else:
            await update.message.reply_text(
                f"❌ Ошибка при удалении username @{username} из whitelist."
            )
            logger.error(f"Failed to remove username {username} from whitelist")
            
    except Exception as e:
        logger.error(f"Error in admin_remove_username_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")


@require_admin
async def admin_whitelist_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to show whitelist status
    Command: /whitelist
    """
    try:
        # Force reload config to get latest data
        from app.whitelist import _reload_config
        _reload_config()
        
        # Get fresh config reference after reload
        from app import whitelist
        current_config = whitelist.config
        
        if not current_config:
            await update.message.reply_text("❌ Ошибка загрузки конфигурации whitelist.")
            return
        
        # Get config file path for diagnostics
        from app.whitelist import _get_config_file_path
        import os
        config_file = _get_config_file_path()
        config_exists = config_file.exists()
        config_writable = config_file.exists() and os.access(config_file, os.W_OK) if config_file.exists() else False
        
        # Get whitelist status from fresh config
        is_enabled = getattr(current_config, 'ENABLE_WHITELIST', False)
        status_icon = "🟢" if is_enabled else "🔴"
        status_text = "Включен" if is_enabled else "Выключен"
        
        # Get authorized user IDs from fresh config
        authorized_user_ids = getattr(current_config, 'AUTHORIZED_USER_IDS', [])
        authorized_usernames = getattr(current_config, 'AUTHORIZED_USERNAMES', [])
        
        # Get admin user IDs from fresh config
        admin_user_ids = getattr(current_config, 'ADMIN_USER_IDS', [])
        
        # Log what we're reading for debugging
        logger.info(f"Whitelist status - User IDs: {authorized_user_ids}, Usernames: {authorized_usernames}")
        
        # Build status message
        message = f"🔐 **Статус Whitelist**\n\n"
        message += f"📊 **Состояние:** {status_icon} {status_text}\n"
        message += f"👥 **Авторизованных пользователей:** {len(authorized_user_ids)}\n"
        message += f"🏷️ **Авторизованных usernames:** {len(authorized_usernames)}\n\n"
        
        # List authorized user IDs
        if authorized_user_ids:
            message += "📋 **ID пользователей:**\n"
            for uid in authorized_user_ids[:20]:  # Limit to 20 for readability
                admin_marker = " (Админ)" if uid in admin_user_ids else ""
                message += f"• {uid}{admin_marker}\n"
            
            if len(authorized_user_ids) > 20:
                message += f"• ... и еще {len(authorized_user_ids) - 20} пользователей\n"
        else:
            message += "📋 **ID пользователей:** (пусто)\n"
        
        message += "\n"
        
        # List authorized usernames
        if authorized_usernames:
            message += "🏷️ **Usernames:**\n"
            for username in authorized_usernames[:20]:  # Limit to 20 for readability
                message += f"• @{username}\n"
            
            if len(authorized_usernames) > 20:
                message += f"• ... и еще {len(authorized_usernames) - 20} usernames\n"
        else:
            message += "🏷️ **Usernames:** (пусто)\n"
        
        message += "\n"
        message += "💡 **Управление:**\n"
        message += "• `/adduser_123456` - Добавить по ID (постоянно)\n"
        message += "• `/removeuser_123456` - Удалить по ID (постоянно)\n"
        message += "• `/addusername_username` - Добавить по username (постоянно)\n"
        message += "• `/removeusername_username` - Удалить по username (постоянно)\n"
        message += "\n"
        message += "👑 **Администраторы:**\n"
        message += "• `/addadmin_123456` - Добавить администратора\n"
        message += "• `/removeadmin_123456` - Удалить администратора\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")
        logger.info(f"Admin {update.effective_user.id} viewed whitelist status")
        
    except Exception as e:
        logger.error(f"Error in admin_whitelist_status_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при получении статуса whitelist.")


@require_admin
async def admin_add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to permanently add an admin user
    Command: /addadmin_<user_id>
    """
    try:
        user_id = update.effective_user.id
        command_text = update.message.text
        
        # Extract user ID from command
        if '_' not in command_text:
            await update.message.reply_text(
                "❌ Неверный формат команды. Используйте: /addadmin_123456789"
            )
            return
        
        try:
            target_user_id = int(command_text.split('_')[1])
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Неверный формат ID пользователя. Используйте: /addadmin_123456789"
            )
            return
        
        # Check if user is already an admin (get fresh config)
        from app import whitelist
        current_config = whitelist.config
        if current_config and hasattr(current_config, 'ADMIN_USER_IDS'):
            if target_user_id in current_config.ADMIN_USER_IDS:
                await update.message.reply_text(
                    f"ℹ️ Пользователь {target_user_id} уже является администратором."
                )
                return
        
        # Add admin to permanent config
        success = add_admin_to_permanent_config(target_user_id)
        
        if success:
            await update.message.reply_text(
                f"✅ Пользователь {target_user_id} добавлен в список администраторов!\n\n"
                f"👑 Пользователь теперь имеет права администратора.\n"
                f"📝 ID администратора добавлен в whitelist_config.py и сохранится после перезапуска бота."
            )
            logger.info(f"Admin {user_id} added user {target_user_id} as admin")
        else:
            await update.message.reply_text(
                f"❌ Ошибка при добавлении администратора {target_user_id}."
            )
            logger.error(f"Failed to add admin {target_user_id}")
            
    except Exception as e:
        logger.error(f"Error in admin_add_admin_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")


@require_admin
async def admin_remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to permanently remove an admin user
    Command: /removeadmin_<user_id>
    """
    try:
        user_id = update.effective_user.id
        command_text = update.message.text
        
        # Extract user ID from command
        if '_' not in command_text:
            await update.message.reply_text(
                "❌ Неверный формат команды. Используйте: /removeadmin_123456789"
            )
            return
        
        try:
            target_user_id = int(command_text.split('_')[1])
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Неверный формат ID пользователя. Используйте: /removeadmin_123456789"
            )
            return
        
        # Prevent self-removal
        if target_user_id == user_id:
            await update.message.reply_text(
                "❌ Вы не можете удалить себя из списка администраторов."
            )
            return
        
        # Check if user is an admin (get fresh config)
        from app import whitelist
        current_config = whitelist.config
        if current_config and hasattr(current_config, 'ADMIN_USER_IDS'):
            if target_user_id not in current_config.ADMIN_USER_IDS:
                await update.message.reply_text(
                    f"ℹ️ Пользователь {target_user_id} не является администратором."
                )
                return
        
        # Remove admin from permanent config
        success = remove_admin_from_permanent_config(target_user_id)
        
        if success:
            await update.message.reply_text(
                f"✅ Пользователь {target_user_id} удален из списка администраторов.\n\n"
                f"🔄 Изменения сохранены в whitelist_config.py."
            )
            logger.info(f"Admin {user_id} removed user {target_user_id} from admin list")
        else:
            await update.message.reply_text(
                f"❌ Ошибка при удалении администратора {target_user_id}."
            )
            logger.error(f"Failed to remove admin {target_user_id}")
            
    except Exception as e:
        logger.error(f"Error in admin_remove_admin_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")

