from decimal import Decimal
from db.database import get_session
from db.models import (
    Submission, Prediction, Transaction,
    TransactionType, SubmissionStatus, Currency, User, Game, GameStatus
)


def get_user_balance(telegram_id: int, currency: str) -> Decimal:
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return Decimal("0")
        return user.balance_usdt if currency == "usdt" else user.balance_token
    finally:
        session.close()


def submit_prediction(
    telegram_id: int,
    picks: list[dict],
    entry_fee: Decimal,
    currency: str,
) -> dict:
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return {"error": "User not found."}

        balance = user.balance_usdt if currency == "usdt" else user.balance_token
        if balance < entry_fee:
            return {"error": f"Insufficient balance. You have {balance} {currency.upper()}."}

        if currency == "usdt":
            user.balance_usdt -= entry_fee
        else:
            user.balance_token -= entry_fee

        submission = Submission(
            user_id=user.id,
            entry_fee=entry_fee,
            currency=Currency[currency],
            status=SubmissionStatus.pending,
        )
        session.add(submission)
        session.flush()

        for pick in picks:
            prediction = Prediction(
                submission_id=submission.id,
                game_id=pick["game_id"],
                predicted_home_score=pick["home_score"],
                predicted_away_score=pick["away_score"],
            )
            session.add(prediction)

        tx = Transaction(
            user_id=user.id,
            type=TransactionType.bet,
            amount=entry_fee,
            currency=Currency[currency],
        )
        session.add(tx)

        session.commit()
        return {"success": True, "submission_id": submission.id}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_submissions(telegram_id: int, page: int = 1, per_page: int = 5) -> dict:
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return {"submissions": [], "total": 0, "page": page}

        total = session.query(Submission).filter_by(user_id=user.id).count()
        submissions = (
            session.query(Submission)
            .filter_by(user_id=user.id)
            .order_by(Submission.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        result = []
        for sub in submissions:
            preds = []
            for pred in sub.predictions:
                game = session.query(Game).filter_by(id=pred.game_id).first()
                preds.append({
                    "game": f"{game.home_team} vs {game.away_team}" if game else "Unknown",
                    "predicted": f"{pred.predicted_home_score}-{pred.predicted_away_score}",
                    "actual": (
                        f"{game.actual_home_score}-{game.actual_away_score}"
                        if game and game.actual_home_score is not None else "Pending"
                    ),
                    "result": pred.result.value,
                })
            result.append({
                "id": sub.id,
                "status": sub.status.value,
                "entry_fee": str(sub.entry_fee),
                "currency": sub.currency.value,
                "payout": str(sub.payout_amount) if sub.payout_amount else None,
                "date": sub.created_at.strftime("%Y-%m-%d %H:%M"),
                "picks": preds,
            })

        return {"submissions": result, "total": total, "page": page, "per_page": per_page}
    finally:
        session.close()
