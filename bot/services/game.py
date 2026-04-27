from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from db.database import get_session
from db.models import Game, GameStatus, Submission, SubmissionStatus, Prediction, PredictionResult, Transaction, TransactionType, User
from bot.utils import adjust_balance


def create_game(league: str, home_team: str, away_team: str, kickoff_time: datetime, admin_id: int) -> Game:
    with get_session() as session:
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


def close_game(game_id: int) -> Game | None:
    with get_session() as session:
        game = session.query(Game).filter_by(id=game_id).first()
        if not game:
            return None
        game.status = GameStatus.closed
        session.commit()
        session.refresh(game)
        return game


def post_result(game_id: int, home_score: int, away_score: int) -> dict:
    with get_session() as session:
        game = session.query(Game).filter_by(id=game_id).first()
        if not game:
            return {"error": "Game not found"}

        game.actual_home_score = home_score
        game.actual_away_score = away_score
        game.status = GameStatus.settled

        predictions = session.query(Prediction).filter_by(game_id=game_id).all()

        preds_by_submission: dict[int, list] = defaultdict(list)
        for prediction in predictions:
            correct = (
                prediction.predicted_home_score == home_score
                and prediction.predicted_away_score == away_score
            )
            prediction.result = PredictionResult.win if correct else PredictionResult.loss
            preds_by_submission[prediction.submission_id].append(prediction)

        session.flush()

        submissions = session.query(Submission).filter(
            Submission.id.in_(preds_by_submission.keys())
        ).all()
        winners = 0

        for submission in submissions:
            if submission.status != SubmissionStatus.pending:
                continue
            sub_preds = preds_by_submission[submission.id]
            all_correct = all(p.result == PredictionResult.win for p in sub_preds)

            if all_correct:
                submission.status = SubmissionStatus.won
                payout = Decimal(submission.entry_fee) * Decimal("2.5")
                submission.payout_amount = payout
                user = session.query(User).filter_by(id=submission.user_id).first()
                if user:
                    adjust_balance(user, submission.currency.value, payout)
                    session.add(Transaction(
                        user_id=user.id,
                        type=TransactionType.reward,
                        amount=payout,
                        currency=submission.currency,
                    ))
                winners += 1
            else:
                submission.status = SubmissionStatus.lost

        session.commit()
        return {"settled": len(predictions), "winners": winners}


def get_active_games() -> list[Game]:
    with get_session() as session:
        return session.query(Game).filter_by(status=GameStatus.active).order_by(Game.league, Game.kickoff_time).all()


def get_all_games() -> list[Game]:
    with get_session() as session:
        return session.query(Game).order_by(Game.created_at.desc()).limit(50).all()


def get_all_users() -> list[User]:
    with get_session() as session:
        return session.query(User).order_by(User.created_at.desc()).all()
