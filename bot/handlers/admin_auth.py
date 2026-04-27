from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import settings


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in settings.ADMIN_IDS:
            await update.message.reply_text("Access denied.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
