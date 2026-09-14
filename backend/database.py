from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float, UniqueConstraint, Index
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime, timezone
import json

from config import settings

DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    quizzes = relationship("Quiz", back_populates="owner", cascade="all, delete-orphan")
    attempts = relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        # Each user gets their own copy of a quiz for a given (URL,
        # question_count, difficulty) combination -- not just URL alone.
        # Without question_count/difficulty in the key, requesting the
        # same article again with different settings would either
        # silently return the old quiz (ignoring the new settings) or
        # hit a 409 conflict on the old (owner_id, url)-only constraint.
        UniqueConstraint(
            "owner_id", "url", "question_count", "difficulty",
            name="uq_quizzes_owner_url_params",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Nullable: a quiz generated from an uploaded document has no source
    # URL. source_type distinguishes how to interpret this row.
    url = Column(String, nullable=True, index=True)
    source_type = Column(String, nullable=False, default="wikipedia", server_default="wikipedia")
    # The resolved generation parameters actually used, so re-requesting
    # the same source with different settings creates a distinct quiz
    # rather than colliding with an old one. Nullable so pre-existing rows
    # from before this feature existed don't need backfilling with a
    # guessed value -- they simply never match new parameterized requests.
    question_count = Column(Integer, nullable=True)
    difficulty = Column(String, nullable=True)
    title = Column(String, nullable=False)
    date_generated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    scraped_content = Column(Text)
    full_quiz_data = Column(Text)

    owner = relationship("User", back_populates="quizzes")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")
    
    def set_quiz_data(self, data: dict):
        self.full_quiz_data = json.dumps(data)
    
    def get_quiz_data(self) -> dict:
        return json.loads(self.full_quiz_data) if self.full_quiz_data else {}

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("ix_quiz_attempts_quiz_id_date", "quiz_id", "date_attempted"),
    )

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    user_answers = Column(JSON, nullable=False)
    time_taken = Column(Integer, default=0)
    date_attempted = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    quiz = relationship("Quiz", back_populates="attempts")
    user = relationship("User", back_populates="attempts")

# NOTE: Schema is managed by Alembic migrations (see backend/alembic/), not by
# create_all() at import time. Import-time table creation silently swallowed
# errors and made schema changes impossible to track or roll back safely.
# Run `alembic upgrade head` before starting the app (handled by
# docker-entrypoint.sh / the CI deploy step).

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()