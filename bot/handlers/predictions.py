from decimal import Decimal
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.constants import (
    PICK_STEP, PICK_GAMES, PICK_SELECTED, PICK_SCORES, PICK_SCORE_INDEX,
    PICK_STATE_SELECTING, PICK_STATE_SCORING, PICK_STATE_CONFIRMING,
)
from bot.utils import parse_score, reply_or_edit
from bot.services.game import get_active_games
from bot.services.prediction import submit_prediction, get_user_submissions, get_user_balance

ENTRY_FEE = Decimal("1.00")
ENTRY_CURRENCY = "usdt"
PICKS_REQUIRED = 3


def _clear_pick_state(context: ContextTypes.DEFAULT_TYPE):
    for key in (PICK_STEP, PICK_SELECTED, PICK_SCORES, PICK_GAMES, PICK_SCORE_INDEX):
        context.user_data.pop(key, None)


async def pickgames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    games = get_active_games()

    if not games:
        await update.message.reply_text("No active games right now. Check back later.")
        return

    context.user_data[PICK_GAMES] = {
        game.id: {
            "id": game.id,
            "league": game.league,
            "home": game.home_team,
            "away": game.away_team,
            "kickoff": game.kickoff_time.strftime("%Y-%m-%d %H:%M"),
        }
        for game in games
    }
    context.user_data[PICK_SELECTED] = []
    context.user_data[PICK_SCORES] = []
    context.user_data[PICK_STEP] = PICK_STATE_SELECTING

    await _send_game_list(update, context)


async def _send_game_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    games = context.user_data.get(PICK_GAMES, {})
    selected = context.user_data.get(PICK_SELECTED, [])

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
                f"{marker}{game['home']} vs {game['away']}",
                callback_data=f"pick_{game['id']}",
            )
        ])

    if len(selected) == PICKS_REQUIRED:
        keyboard.append([InlineKeyboardButton("Submit Picks", callback_data="pick_submit")])

    await reply_or_edit(update, "\n".join(text_lines), InlineKeyboardMarkup(keyboard))


async def handle_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "pick_submit":
        selected = context.user_data.get(PICK_SELECTED, [])
        if len(selected) != PICKS_REQUIRED:
            await query.answer(f"Select exactly {PICKS_REQUIRED} games.", show_alert=True)
            return
        context.user_data[PICK_STEP] = PICK_STATE_SCORING
        context.user_data[PICK_SCORE_INDEX] = 0
        await _ask_for_score(update, context)
        return

    if data.startswith("pick_"):
        game_id = int(data.split("_")[1])
        selected = context.user_data.get(PICK_SELECTED, [])

        if game_id in selected:
            selected.remove(game_id)
        else:
            if len(selected) >= PICKS_REQUIRED:
                await query.answer(f"You can only pick {PICKS_REQUIRED} games.", show_alert=True)
                return
            selected.append(game_id)

        context.user_data[PICK_SELECTED] = selected
        await _send_game_list(update, context)
        return

    if data.startswith("result_page_"):
        page = int(data.split("_")[2])
        await _send_results_page(update, context, page)


async def _ask_for_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected = context.user_data.get(PICK_SELECTED, [])
    index = context.user_data.get(PICK_SCORE_INDEX, 0)
    games = context.user_data.get(PICK_GAMES, {})
    game = games[selected[index]]

    text = (
        f"Game {index + 1} of {PICKS_REQUIRED}\n\n"
        f"{game['league']}\n"
        f"{game['home']} vs {game['away']}\n"
        f"Kickoff: {game['kickoff']} UTC\n\n"
        f"Enter your predicted score (format: home-away)\n"
        f"Example: 2-1"
    )
    await reply_or_edit(update, text)


async def handle_score_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get(PICK_STEP) != PICK_STATE_SCORING:
        return False

    score = parse_score(update.message.text)
    if score is None:
        await update.message.reply_text("Invalid score. Use format: 2-1")
        return True

    selected = context.user_data.get(PICK_SELECTED, [])
    index = context.user_data.get(PICK_SCORE_INDEX, 0)
    games = context.user_data.get(PICK_GAMES, {})
    scores = context.user_data.get(PICK_SCORES, [])

    scores.append({"game_id": selected[index], "home_score": score[0], "away_score": score[1]})
    context.user_data[PICK_SCORES] = scores
    context.user_data[PICK_SCORE_INDEX] = index + 1

    if index + 1 < PICKS_REQUIRED:
        await _ask_for_score(update, context)
        return True

    context.user_data[PICK_STEP] = PICK_STATE_CONFIRMING
    lines = ["Your picks:\n"]
    for i, s in enumerate(scores):
        game = games[selected[i]]
        lines.append(
            f"{i + 1}. {game['home']} vs {game['away']}\n"
            f"   Your score: {s['home_score']}-{s['away_score']}\n"
        )

    balance = get_user_balance(update.effective_user.id, ENTRY_CURRENCY)
    lines.append(f"\nEntry fee: {ENTRY_FEE} {ENTRY_CURRENCY.upper()}")
    lines.append(f"Your balance: {balance} {ENTRY_CURRENCY.upper()}")
    lines.append("\nType CONFIRM to submit or CANCEL to discard.")

    await update.message.reply_text("\n".join(lines))
    return True


async def handle_prediction_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get(PICK_STEP) != PICK_STATE_CONFIRMING:
        return False

    text = update.message.text.strip().upper()

    if text == "CANCEL":
        _clear_pick_state(context)
        await update.message.reply_text("Picks discarded.")
        return True

    if text != "CONFIRM":
        await update.message.reply_text("Type CONFIRM to submit or CANCEL to discard.")
        return True

    picks = [
        {"game_id": s["game_id"], "home_score": s["home_score"], "away_score": s["away_score"]}
        for s in context.user_data[PICK_SCORES]
    ]

    result = submit_prediction(
        telegram_id=update.effective_user.id,
        picks=picks,
        entry_fee=ENTRY_FEE,
        currency=ENTRY_CURRENCY,
    )

    _clear_pick_state(context)

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
    data = get_user_submissions(update.effective_user.id, page=page)

    submissions = data["submissions"]
    total = data["total"]
    per_page = data["per_page"]
    total_pages = max(1, (total + per_page - 1) // per_page)

    if not submissions:
        await reply_or_edit(update, "You have no prediction history yet.")
        return

    lines = [f"Your Prediction History (Page {page}/{total_pages})\n"]

    for sub in submissions:
        payout_line = f" | Payout: {sub['payout']} {sub['currency'].upper()}" if sub["payout"] else ""
        lines.append(
            f"Submission {sub['id']} | {sub['date']} | {sub['status'].upper()}\n"
            f"Entry: {sub['entry_fee']} {sub['currency'].upper()}{payout_line}\n"
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
    await reply_or_edit(update, "\n".join(lines), reply_markup)
