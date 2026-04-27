from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)
from config.settings import settings
from db.database import init_db
from bot.handlers.start import (
    start,
    export_wallet,
    export_wallet_confirm,
    import_wallet,
    import_wallet_key,
)


def main():
    init_db()

    app = ApplicationBuilder().token(settings.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("exportwallet", export_wallet))
    app.add_handler(CommandHandler("importwallet", import_wallet))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            _route_text,
        )
    )

    print("Bot is running...")
    app.run_polling()


async def _route_text(update, context):
    user_data = context.user_data

    if user_data.get("awaiting_export_confirm"):
        from bot.handlers.start import export_wallet_confirm
        await export_wallet_confirm(update, context)
        return

    if user_data.get("awaiting_import_key"):
        from bot.handlers.start import import_wallet_key
        await import_wallet_key(update, context)
        return


if __name__ == "__main__":
    main()
