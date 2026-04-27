from db.database import get_session
from db.models import User
from bot.services.wallet import generate_wallet


def get_or_create_user(telegram_id: int, username: str, referral_code: str = None) -> tuple[User, bool]:
    with get_session() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            return user, False

        wallet_address, encrypted_key = generate_wallet()

        referred_by = None
        if referral_code:
            referrer = session.query(User).filter_by(telegram_id=int(referral_code)).first()
            if referrer:
                referred_by = referrer.id

        user = User(
            telegram_id=telegram_id,
            username=username,
            wallet_address=wallet_address,
            encrypted_private_key=encrypted_key,
            referred_by=referred_by,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user, True
