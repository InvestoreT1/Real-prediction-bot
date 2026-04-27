from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.admin_auth import admin_only
from bot.services.game import (
    create_game, close_game, post_result,
    get_all_games, get_all_users,
)

LEAGUES = ["Premier League", "Serie A", "Bundesliga", "La Liga"]

ADD_GAME_STEPS = ["league", "home_team", "away_team", "kickoff_time"]


@admin_only
async def addgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["addgame"] = {}
    league_list = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(LEAGUES))
    await update.message.reply_text(
        f"Add New Game\n\nSelect league by number:\n{league_list}"
    )
    context.user_data["addgame_step"] = "league"


@admin_only
async def closegame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /closegame <game_id>")
        return

    game = close_game(int(args[0]))
    if not game:
        await update.message.reply_text("Game not found.")
        return

    await update.message.reply_text(
        f"Game closed.\n{game.home_team} vs {game.away_team} is no longer accepting predictions."
    )


@admin_only
async def postresult(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2 or not args[0].isdigit():
        await update.message.reply_text("Usage: /postresult <game_id> <home_score>-<away_score>\nExample: /postresult 3 2-1")
        return

    game_id = int(args[0])
    score_str = args[1]

    if "-" not in score_str:
        await update.message.reply_text("Score format must be home-away. Example: 2-1")
        return

    parts = score_str.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await update.message.reply_text("Invalid score. Use format: 2-1")
        return

    home_score = int(parts[0])
    away_score = int(parts[1])

    result = post_result(game_id, home_score, away_score)

    if "error" in result:
        await update.message.reply_text(result["error"])
        return

    await update.message.reply_text(
        f"Result posted.\n\nPredictions settled: {result['settled']}\nWinners paid out: {result['winners']}"
    )


@admin_only
async def listgames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    games = get_all_games()
    if not games:
        await update.message.reply_text("No games found.")
        return

    lines = ["Recent Games\n"]
    for g in games:
        score = ""
        if g.actual_home_score is not None:
            score = f" | Result: {g.actual_home_score}-{g.actual_away_score}"
        lines.append(
            f"ID {g.id} | {g.league}\n"
            f"{g.home_team} vs {g.away_team}\n"
            f"Kickoff: {g.kickoff_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
            f"Status: {g.status.value}{score}\n"
        )

    await update.message.reply_text("\n".join(lines))


@admin_only
async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        await update.message.reply_text("No users found.")
        return

    lines = [f"Total users: {len(users)}\n"]
    for u in users:
        username = f"@{u.username}" if u.username else f"ID {u.telegram_id}"
        lines.append(
            f"{username}\n"
            f"Wallet: {u.wallet_address[:12]}...\n"
            f"USDT: {u.balance_usdt} | Token: {u.balance_token}\n"
        )

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n... (truncated)"

    await update.message.reply_text(text)


@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <your message>")
        return

    context.user_data["broadcast_message"] = " ".join(context.args)
    context.user_data["awaiting_broadcast_confirm"] = True
    await update.message.reply_text(
        f"Message preview:\n\n{context.user_data['broadcast_message']}\n\nType SEND to broadcast or anything else to cancel."
    )


async def handle_addgame_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("addgame_step")
    if not step:
        return False

    data = context.user_data.get("addgame", {})
    text = update.message.text.strip()

    if step == "league":
        if not text.isdigit() or int(text) not in range(1, len(LEAGUES) + 1):
            await update.message.reply_text("Please enter a number between 1 and 4.")
            return True
        data["league"] = LEAGUES[int(text) - 1]
        context.user_data["addgame"] = data
        context.user_data["addgame_step"] = "home_team"
        await update.message.reply_text("Enter the home team name:")
        return True

    if step == "home_team":
        data["home_team"] = text
        context.user_data["addgame"] = data
        context.user_data["addgame_step"] = "away_team"
        await update.message.reply_text("Enter the away team name:")
        return True

    if step == "away_team":
        data["away_team"] = text
        context.user_data["addgame"] = data
        context.user_data["addgame_step"] = "kickoff_time"
        await update.message.reply_text("Enter kickoff time (format: YYYY-MM-DD HH:MM in UTC):")
        return True

    if step == "kickoff_time":
        try:
            kickoff = datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text("Invalid format. Use: YYYY-MM-DD HH:MM")
            return True

        data["kickoff_time"] = kickoff
        context.user_data.pop("addgame_step")
        context.user_data.pop("addgame")

        game = create_game(
            league=data["league"],
            home_team=data["home_team"],
            away_team=data["away_team"],
            kickoff_time=data["kickoff_time"],
            admin_id=update.effective_user.id,
        )

        await update.message.reply_text(
            f"Game added successfully.\n\n"
            f"ID: {game.id}\n"
            f"League: {game.league}\n"
            f"{game.home_team} vs {game.away_team}\n"
            f"Kickoff: {game.kickoff_time.strftime('%Y-%m-%d %H:%M')} UTC"
        )
        return True

    return False


async def handle_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("awaiting_broadcast_confirm"):
        return False

    context.user_data.pop("awaiting_broadcast_confirm")
    message = context.user_data.pop("broadcast_message", "")

    if update.message.text.strip().upper() != "SEND":
        await update.message.reply_text("Broadcast cancelled.")
        return True

    from bot.services.game import get_all_users
    users = get_all_users()
    sent = 0
    failed = 0

    for user in users:
        try:
            await context.bot.send_message(chat_id=user.telegram_id, text=message)
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"Broadcast done.\nSent: {sent} | Failed: {failed}")
    return True
