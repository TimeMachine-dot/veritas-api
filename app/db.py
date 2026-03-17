from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

Base = declarative_base()

engine = None
SessionLocal = None

if settings.database_url:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    if SessionLocal is None:
        return None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if engine is not None:
        Base.metadata.create_all(bind=engine)