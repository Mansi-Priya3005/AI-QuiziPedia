import os
from unittest.mock import AsyncMock, patch


def test_generate_quiz_rate_limit_returns_429(monkeypatch, sample_quiz_output):
    """Uses its own low limit + a fresh app import so it doesn't interfere
    with the shared high limit used by the rest of the suite."""
    monkeypatch.setenv("GENERATE_QUIZ_RATE_LIMIT", "2/minute")

    import importlib
    import config
    import main as main_module

    importlib.reload(config)
    importlib.reload(main_module)

    from fastapi.testclient import TestClient
    from database import get_db
    import tests.conftest as conftest_mod

    # reuse the same DB override pattern as the `client` fixture
    from sqlalchemy.orm import sessionmaker

    engine = __import__("sqlalchemy").create_engine(os.environ["DATABASE_URL"])
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(main_module.app)

    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("text", "T")),
    ), patch.object(
        main_module.quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        statuses = []
        for i in range(4):
            r = test_client.post(
                "/generate-quiz",
                json={"url": f"https://en.wikipedia.org/wiki/Rate_Limit_Test_{i}"},
            )
            statuses.append(r.status_code)

    assert statuses.count(429) >= 1, f"expected at least one 429, got {statuses}"

    # restore the shared high limit for the rest of the suite
    main_module.app.dependency_overrides.clear()
    os.environ["GENERATE_QUIZ_RATE_LIMIT"] = "1000/minute"
    importlib.reload(config)
    importlib.reload(main_module)
