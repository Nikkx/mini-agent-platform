from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./agents.db"

# Connect to the SQLite file
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Provide a SQLAlchemy session generator for use as a FastAPI dependency.

    Yields:
    - A `Session` instance bound to the application's engine.

    Notes:
    Ensures the session is closed after the request scope.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
