from decimal import Decimal
from telegram import Update, InlineKeyboardMarkup


def parse_score(score_str: str) -> tuple[int, int] | None:
    parts = score_str.strip().split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    return int(parts[0]), int(parts[1])


def adjust_balance(user, currency: str, amount: Decimal, deduct: bool = False):
    delta = -amount if deduct else amount
    if currency == "usdt":
        user.balance_usdt += delta
    else:
        user.balance_token += delta


async def reply_or_edit(update: Update, text: str, reply_markup: InlineKeyboardMarkup = None):
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
