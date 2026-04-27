from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from config.settings import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()
