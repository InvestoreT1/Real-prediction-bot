from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from bot.services.user import get_or_create_user
from bot.services.wallet import get_private_key_for_user, import_wallet_for_user

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["Pick Games", "Previous Result"],
        ["Wallet / Balance", "Referral"],
    ],
    resize_keyboard=True,
)

INTRO_TEXT = (
    "Welcome to RealFlow Games\n\n"
    "Your daily football prediction platform.\n\n"
    "How it works:\n"
    "Admin posts 20 games daily from the top 4 leagues.\n"
    "You pick 3 games and predict the correct score for each.\n"
    "Pay a small entry fee to submit your picks.\n"
    "Get all 3 correct and you win.\n\n"
    "Payments run on Solana. Your wallet is created automatically.\n\n"
    "Choose an option below to get started."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referral_code = args[0] if args else None

    _, is_new = get_or_create_user(
        telegram_id=user.id,
        username=user.username or user.first_name,
        referral_code=referral_code,
    )

    if is_new:
        welcome = f"Hey {user.first_name}, your Solana wallet has been created.\n\n" + INTRO_TEXT
    else:
        welcome = f"Welcome back {user.first_name}.\n\n" + INTRO_TEXT

    await update.message.reply_text(welcome, reply_markup=MAIN_MENU)


async def export_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["awaiting_export_confirm"] = True
    await update.message.reply_text(
        "This will send your private key in this chat.\n\n"
        "Anyone with your private key has full access to your wallet and funds.\n\n"
        "Type CONFIRM to proceed or anything else to cancel."
    )


async def export_wallet_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_export_confirm"):
        return

    context.user_data.pop("awaiting_export_confirm")

    if update.message.text.strip().upper() != "CONFIRM":
        await update.message.reply_text("Export cancelled.")
        return

    private_key = get_private_key_for_user(update.effective_user.id)
    if not private_key:
        await update.message.reply_text("Could not retrieve your wallet. Contact support.")
        return

    await update.message.reply_text(
        f"Your private key (base58):\n\n`{private_key}`\n\n"
        "Store this somewhere safe and delete this message.",
        parse_mode="Markdown",
    )


async def import_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_import_key"] = True
    await update.message.reply_text(
        "Send your Solana private key in base58 format.\n\n"
        "This will replace your current bot wallet.\n"
        "Your existing balance will remain linked to your account."
    )


async def import_wallet_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_import_key"):
        return

    context.user_data.pop("awaiting_import_key")
    private_key_b58 = update.message.text.strip()

    wallet_address = import_wallet_for_user(update.effective_user.id, private_key_b58)
    if not wallet_address:
        await update.message.reply_text(
            "Invalid private key. Import failed. Please check and try again."
        )
        return

    await update.message.reply_text(
        f"Wallet imported successfully.\n\nNew address:\n`{wallet_address}`",
        parse_mode="Markdown",
    )
