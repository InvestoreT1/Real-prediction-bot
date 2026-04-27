from decimal import Decimal
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.services.game import get_active_games
from bot.services.prediction import submit_prediction, get_user_submissions, get_user_balance

ENTRY_FEE = Decimal("1.00")
ENTRY_CURRENCY = "usdt"
PICKS_REQUIRED = 3


async def pickgames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    games = get_active_games()

    if not games:
        await update.message.reply_text("No active games right now. Check back later.")
        return

    context.user_data["pick_games"] = {}
    context.user_data["pick_selected"] = []
    context.user_data["pick_scores"] = []
    context.user_data["pick_step"] = "selecting"

    for game in games:
        context.user_data["pick_games"][game.id] = {
            "id": game.id,
            "league": game.league,
            "home": game.home_team,
            "away": game.away_team,
            "kickoff": game.kickoff_time.strftime("%Y-%m-%d %H:%M"),
        }

    await _send_game_list(update, context)


async def _send_game_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    games = context.user_data.get("pick_games", {})
    selected = context.user_data.get("pick_selected", [])

    current_league = None
    text_lines = [
        f"Select {PICKS_REQUIRED} games to predict.\n"
        f"Entry fee: {ENTRY_FEE} {ENTRY_CURRENCY.upper()} per submission.\n"
        f"Selected: {len(selected)}/{PICKS_REQUIRED}\n"
    ]

    keyboard = []
    for game in games.values():
        if game["league"] != current_league:
            current_league = game["league"]
            text_lines.append(f"\n{current_league}")

        is_selected = game["id"] in selected
        marker = "✓ " if is_selected else ""
        text_lines.append(f"{marker}{game['home']} vs {game['away']} | {game['kickoff']} UTC")
        keyboard.append([
            InlineKeyboardButton(
                f"{'✓ ' if is_selected else ''}{game['home']} vs {game['away']}",
                callback_data=f"pick_{game['id']}",
            )
        ])

    if len(selected) == PICKS_REQUIRED:
        keyboard.append([InlineKeyboardButton("Submit Picks", callback_data="pick_submit")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text("\n".join(text_lines), reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("\n".join(text_lines), reply_markup=reply_markup)


async def handle_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "pick_submit":
        selected = context.user_data.get("pick_selected", [])
        if len(selected) != PICKS_REQUIRED:
            await query.answer(f"Select exactly {PICKS_REQUIRED} games.", show_alert=True)
            return
        context.user_data["pick_step"] = "scoring"
        context.user_data["pick_score_index"] = 0
        await _ask_for_score(update, context)
        return

    if data.startswith("pick_"):
        game_id = int(data.split("_")[1])
        selected = context.user_data.get("pick_selected", [])

        if game_id in selected:
            selected.remove(game_id)
        else:
            if len(selected) >= PICKS_REQUIRED:
                await query.answer(f"You can only pick {PICKS_REQUIRED} games.", show_alert=True)
                return
            selected.append(game_id)

        context.user_data["pick_selected"] = selected
        await _send_game_list(update, context)

    if data.startswith("result_page_"):
        page = int(data.split("_")[2])
        await _send_results_page(update, context, page)


async def _ask_for_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = context.user_data.get("pick_selected", [])
    index = context.user_data.get("pick_score_index", 0)
    games = context.user_data.get("pick_games", {})

    game = games[selected[index]]
    context.user_data["pick_step"] = "scoring"

    text = (
        f"Game {index + 1} of {PICKS_REQUIRED}\n\n"
        f"{game['league']}\n"
        f"{game['home']} vs {game['away']}\n"
        f"Kickoff: {game['kickoff']} UTC\n\n"
        f"Enter your predicted score (format: home-away)\n"
        f"Example: 2-1"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def handle_score_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("pick_step") != "scoring":
        return False

    text = update.message.text.strip()

    if "-" not in text:
        await update.message.reply_text("Use format home-away. Example: 2-1")
        return True

    parts = text.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await update.message.reply_text("Invalid score. Use format: 2-1")
        return True

    home_score = int(parts[0])
    away_score = int(parts[1])

    selected = context.user_data.get("pick_selected", [])
    index = context.user_data.get("pick_score_index", 0)
    games = context.user_data.get("pick_games", {})
    scores = context.user_data.get("pick_scores", [])

    scores.append({
        "game_id": selected[index],
        "home_score": home_score,
        "away_score": away_score,
    })
    context.user_data["pick_scores"] = scores
    context.user_data["pick_score_index"] = index + 1

    if index + 1 < PICKS_REQUIRED:
        await _ask_for_score(update, context)
        return True

    context.user_data["pick_step"] = "confirming"
    scores_list = context.user_data["pick_scores"]

    lines = ["Your picks:\n"]
    for i, score in enumerate(scores_list):
        game = games[selected[i]]
        lines.append(
            f"{i + 1}. {game['home']} vs {game['away']}\n"
            f"   Your score: {score['home_score']}-{score['away_score']}\n"
        )

    balance = get_user_balance(update.effective_user.id, ENTRY_CURRENCY)
    lines.append(f"\nEntry fee: {ENTRY_FEE} {ENTRY_CURRENCY.upper()}")
    lines.append(f"Your balance: {balance} {ENTRY_CURRENCY.upper()}")
    lines.append("\nType CONFIRM to submit or CANCEL to discard.")

    await update.message.reply_text("\n".join(lines))
    return True


async def handle_prediction_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("pick_step") != "confirming":
        return False

    text = update.message.text.strip().upper()

    if text == "CANCEL":
        context.user_data.pop("pick_step", None)
        context.user_data.pop("pick_selected", None)
        context.user_data.pop("pick_scores", None)
        context.user_data.pop("pick_games", None)
        context.user_data.pop("pick_score_index", None)
        await update.message.reply_text("Picks discarded.")
        return True

    if text != "CONFIRM":
        await update.message.reply_text("Type CONFIRM to submit or CANCEL to discard.")
        return True

    picks = [
        {
            "game_id": s["game_id"],
            "home_score": s["home_score"],
            "away_score": s["away_score"],
        }
        for s in context.user_data["pick_scores"]
    ]

    result = submit_prediction(
        telegram_id=update.effective_user.id,
        picks=picks,
        entry_fee=ENTRY_FEE,
        currency=ENTRY_CURRENCY,
    )

    context.user_data.pop("pick_step", None)
    context.user_data.pop("pick_selected", None)
    context.user_data.pop("pick_scores", None)
    context.user_data.pop("pick_games", None)
    context.user_data.pop("pick_score_index", None)

    if "error" in result:
        await update.message.reply_text(f"Submission failed.\n{result['error']}")
        return True

    await update.message.reply_text(
        f"Picks submitted successfully.\n\n"
        f"Submission ID: {result['submission_id']}\n"
        f"Entry fee of {ENTRY_FEE} {ENTRY_CURRENCY.upper()} deducted.\n\n"
        f"Good luck! Results will be posted after the games."
    )
    return True


async def previousresult(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_results_page(update, context, page=1)


async def _send_results_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    telegram_id = update.effective_user.id
    data = get_user_submissions(telegram_id, page=page)

    submissions = data["submissions"]
    total = data["total"]
    per_page = data["per_page"]
    total_pages = max(1, (total + per_page - 1) // per_page)

    if not submissions:
        text = "You have no prediction history yet."
        if update.message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return

    lines = [f"Your Prediction History (Page {page}/{total_pages})\n"]

    for sub in submissions:
        status_label = sub["status"].upper()
        payout_line = f"Payout: {sub['payout']} {sub['currency'].upper()}" if sub["payout"] else ""
        lines.append(
            f"Submission {sub['id']} | {sub['date']} | {status_label}\n"
            f"Entry: {sub['entry_fee']} {sub['currency'].upper()}"
            + (f" | {payout_line}" if payout_line else "") + "\n"
        )
        for pick in sub["picks"]:
            lines.append(
                f"  {pick['game']}\n"
                f"  Your pick: {pick['predicted']} | Actual: {pick['actual']} | {pick['result'].upper()}\n"
            )
        lines.append("")

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("Previous", callback_data=f"result_page_{page - 1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next", callback_data=f"result_page_{page + 1}"))

    reply_markup = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None
    text = "\n".join(lines)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
