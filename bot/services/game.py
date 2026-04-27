from datetime import datetime
from decimal import Decimal
from db.database import get_session
from db.models import Game, GameStatus, Submission, SubmissionStatus, Prediction, PredictionResult, Transaction, TransactionType, User


def create_game(league: str, home_team: str, away_team: str, kickoff_time: datetime, admin_id: int) -> Game:
    session = get_session()
    try:
        game = Game(
            league=league,
            home_team=home_team,
            away_team=away_team,
            kickoff_time=kickoff_time,
            status=GameStatus.active,
            created_by=admin_id,
        )
        session.add(game)
        session.commit()
        session.refresh(game)
        return game
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_game(game_id: int) -> Game | None:
    session = get_session()
    try:
        game = session.query(Game).filter_by(id=game_id).first()
        if not game:
            return None
        game.status = GameStatus.closed
        session.commit()
        session.refresh(game)
        return game
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def post_result(game_id: int, home_score: int, away_score: int) -> dict:
    session = get_session()
    try:
        game = session.query(Game).filter_by(id=game_id).first()
        if not game:
            return {"error": "Game not found"}

        game.actual_home_score = home_score
        game.actual_away_score = away_score
        game.status = GameStatus.settled

        predictions = session.query(Prediction).filter_by(game_id=game_id).all()
        winners = 0

        for prediction in predictions:
            if (
                prediction.predicted_home_score == home_score
                and prediction.predicted_away_score == away_score
            ):
                prediction.result = PredictionResult.win
            else:
                prediction.result = PredictionResult.loss

        session.flush()

        submissions = (
            session.query(Submission)
            .join(Prediction, Prediction.submission_id == Submission.id)
            .filter(Prediction.game_id == game_id)
            .distinct()
            .all()
        )

        for submission in submissions:
            sub_preds = session.query(Prediction).filter_by(submission_id=submission.id).all()
            all_correct = all(p.result == PredictionResult.win for p in sub_preds)

            if all_correct and submission.status == SubmissionStatus.pending:
                submission.status = SubmissionStatus.won
                payout = Decimal(submission.entry_fee) * Decimal("2.5")
                submission.payout_amount = payout

                user = session.query(User).filter_by(id=submission.user_id).first()
                if user:
                    if submission.currency.value == "usdt":
                        user.balance_usdt += payout
                    else:
                        user.balance_token += payout

                    tx = Transaction(
                        user_id=user.id,
                        type=TransactionType.reward,
                        amount=payout,
                        currency=submission.currency,
                    )
                    session.add(tx)
                winners += 1
            elif submission.status == SubmissionStatus.pending:
                all_settled = all(p.result != PredictionResult.pending for p in sub_preds)
                if all_settled:
                    submission.status = SubmissionStatus.lost

        session.commit()
        return {"settled": len(predictions), "winners": winners}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_active_games() -> list[Game]:
    session = get_session()
    try:
        return session.query(Game).filter_by(status=GameStatus.active).order_by(Game.league, Game.kickoff_time).all()
    finally:
        session.close()


def get_all_games() -> list[Game]:
    session = get_session()
    try:
        return session.query(Game).order_by(Game.created_at.desc()).limit(50).all()
    finally:
        session.close()


def get_all_users() -> list[User]:
    session = get_session()
    try:
        return session.query(User).order_by(User.created_at.desc()).all()
    finally:
        session.close()
