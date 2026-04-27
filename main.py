from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from config.settings import settings
from db.database import init_db
from bot.handlers.start import (
    start,
    export_wallet,
    import_wallet,
)
from bot.handlers.admin import (
    addgame,
    closegame,
    postresult,
    listgames,
    listusers,
    broadcast,
)
from bot.handlers.predictions import (
    pickgames,
    previousresult,
    handle_pick_callback,
)


def main():
    init_db()

    app = ApplicationBuilder().token(settings.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("exportwallet", export_wallet))
    app.add_handler(CommandHandler("importwallet", import_wallet))

    app.add_handler(CommandHandler("addgame", addgame))
    app.add_handler(CommandHandler("closegame", closegame))
    app.add_handler(CommandHandler("postresult", postresult))
    app.add_handler(CommandHandler("listgames", listgames))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(CommandHandler("pickgames", pickgames))
    app.add_handler(CommandHandler("previousresult", previousresult))

    app.add_handler(CallbackQueryHandler(handle_pick_callback, pattern="^pick_"))
    app.add_handler(CallbackQueryHandler(handle_pick_callback, pattern="^result_page_"))

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

    if user_data.get("addgame_step"):
        from bot.handlers.admin import handle_addgame_step
        handled = await handle_addgame_step(update, context)
        if handled:
            return

    if user_data.get("awaiting_broadcast_confirm"):
        from bot.handlers.admin import handle_broadcast_confirm
        await handle_broadcast_confirm(update, context)
        return

    if user_data.get("pick_step") == "scoring":
        from bot.handlers.predictions import handle_score_input
        handled = await handle_score_input(update, context)
        if handled:
            return

    if user_data.get("pick_step") == "confirming":
        from bot.handlers.predictions import handle_prediction_confirm
        await handle_prediction_confirm(update, context)
        return

    text = update.message.text.strip()
    if text == "Pick Games":
        await pickgames(update, context)
    elif text == "Previous Result":
        await previousresult(update, context)


if __name__ == "__main__":
    main()
