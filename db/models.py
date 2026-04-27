from sqlalchemy import (
    Column, Integer, BigInteger, String, Text,
    Numeric, Boolean, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()


class GameStatus(enum.Enum):
    pending = "pending"
    active = "active"
    closed = "closed"
    settled = "settled"


class PredictionResult(enum.Enum):
    pending = "pending"
    win = "win"
    loss = "loss"


class SubmissionStatus(enum.Enum):
    pending = "pending"
    won = "won"
    lost = "lost"


class TransactionType(enum.Enum):
    deposit = "deposit"
    withdraw = "withdraw"
    bet = "bet"
    reward = "reward"
    referral_bonus = "referral_bonus"


class Currency(enum.Enum):
    usdt = "usdt"
    token = "token"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(64))
    encrypted_private_key = Column(Text, nullable=False)
    wallet_address = Column(String(64), unique=True, nullable=False)
    balance_usdt = Column(Numeric(18, 6), default=0)
    balance_token = Column(Numeric(18, 6), default=0)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    referrals = relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer")
    submissions = relationship("Submission", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    league = Column(String(64), nullable=False)
    home_team = Column(String(64), nullable=False)
    away_team = Column(String(64), nullable=False)
    kickoff_time = Column(DateTime, nullable=False)
    actual_home_score = Column(Integer, nullable=True)
    actual_away_score = Column(Integer, nullable=True)
    status = Column(Enum(GameStatus), default=GameStatus.active)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    predictions = relationship("Prediction", back_populates="game")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    predicted_home_score = Column(Integer, nullable=False)
    predicted_away_score = Column(Integer, nullable=False)
    result = Column(Enum(PredictionResult), default=PredictionResult.pending)

    game = relationship("Game", back_populates="predictions")
    submission = relationship("Submission", back_populates="predictions")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_fee = Column(Numeric(18, 6), nullable=False)
    currency = Column(Enum(Currency), nullable=False)
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.pending)
    payout_amount = Column(Numeric(18, 6), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="submissions")
    predictions = relationship("Prediction", back_populates="submission")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(18, 6), nullable=False)
    currency = Column(Enum(Currency), nullable=False)
    tx_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    reward_amount = Column(Numeric(18, 6), nullable=True)
    reward_paid = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="referrals")
