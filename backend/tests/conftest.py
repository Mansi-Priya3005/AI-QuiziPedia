import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/quizipedia_test"
)
os.environ.setdefault("GEMINI_API_KEY", "test-key-for-pytest")
# Rate limiting is tested explicitly in test_rate_limiting.py with its own
# tight limit; the default limit is set high here so the rest of the
# suite (which legitimately calls /generate-quiz many times across many
# tests within the same minute) doesn't flake on 429s.
os.environ.setdefault("GENERATE_QUIZ_RATE_LIMIT", "1000/minute")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import QuizOutput, QuizQuestion


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db(db_engine):
    """Truncate all tables between tests so tests don't leak state into
    each other (e.g. the unique-URL constraint would otherwise make the
    second test using the same fixture URL fail)."""
    with db_engine.begin() as conn:
        conn.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE quiz_attempts, quizzes RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
def client(db_engine):
    import main
    from database import get_db

    TestingSessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def sample_quiz_output():
    return QuizOutput(
        summary="Ada Lovelace was an English mathematician.",
        key_entities={
            "people": ["Ada Lovelace", "Charles Babbage"],
            "organizations": [],
            "locations": ["London"],
        },
        sections=["Early life", "Work with Babbage"],
        quiz=[
            QuizQuestion(
                question=f"Sample question {i}?",
                options=["A) opt1", "B) opt2", "C) opt3", "D) opt4"],
                answer="A",
                difficulty="easy",
                explanation="Because the article says so.",
            )
            for i in range(5)
        ],
        related_topics=["Analytical Engine", "Charles Babbage"],
    )
