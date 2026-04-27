from decimal import Decimal
from sqlalchemy.orm import joinedload
from db.database import get_session
from db.models import (
    Submission, Prediction, Transaction,
    TransactionType, SubmissionStatus, Currency, User
)
from bot.utils import adjust_balance


def get_user_balance(telegram_id: int, currency: str) -> Decimal:
    with get_session() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return Decimal("0")
        return user.balance_usdt if currency == "usdt" else user.balance_token


def submit_prediction(
    telegram_id: int,
    picks: list[dict],
    entry_fee: Decimal,
    currency: str,
) -> dict:
    with get_session() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return {"error": "User not found."}

        balance = user.balance_usdt if currency == "usdt" else user.balance_token
        if balance < entry_fee:
            return {"error": f"Insufficient balance. You have {balance} {currency.upper()}."}

        adjust_balance(user, currency, entry_fee, deduct=True)

        submission = Submission(
            user_id=user.id,
            entry_fee=entry_fee,
            currency=Currency[currency],
            status=SubmissionStatus.pending,
        )
        session.add(submission)
        session.flush()

        for pick in picks:
            session.add(Prediction(
                submission_id=submission.id,
                game_id=pick["game_id"],
                predicted_home_score=pick["home_score"],
                predicted_away_score=pick["away_score"],
            ))

        session.add(Transaction(
            user_id=user.id,
            type=TransactionType.bet,
            amount=entry_fee,
            currency=Currency[currency],
        ))

        session.commit()
        return {"success": True, "submission_id": submission.id}


def get_user_submissions(telegram_id: int, page: int = 1, per_page: int = 5) -> dict:
    with get_session() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return {"submissions": [], "total": 0, "page": page}

        total = session.query(Submission).filter_by(user_id=user.id).count()
        submissions = (
            session.query(Submission)
            .filter_by(user_id=user.id)
            .options(joinedload(Submission.predictions).joinedload(Prediction.game))
            .order_by(Submission.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        result = []
        for sub in submissions:
            preds = []
            for pred in sub.predictions:
                game = pred.game
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
