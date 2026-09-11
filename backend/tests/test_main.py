from unittest.mock import AsyncMock, patch

from llm_quiz_generator import QuizGenerationError
from scraper import ScrapeError


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200


def test_health_check_reports_db_connected(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_generate_quiz_rejects_non_wikipedia_url(client):
    r = client.post("/generate-quiz", json={"url": "https://example.com/not-wiki"})
    assert r.status_code == 422


def test_generate_quiz_happy_path(client, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Ada Lovelace"
    assert len(body["quiz"]) == 5


def test_generate_quiz_deduplicates_same_url(client, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r1 = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
        )
        r2 = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
        )
    assert r1.json()["id"] == r2.json()["id"]


def test_generate_quiz_scrape_failure_returns_400_and_stores_nothing(client):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(side_effect=ScrapeError("That Wikipedia page doesn't exist.")),
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Nonexistent_Xyz"},
        )
    assert r.status_code == 400
    assert client.get("/quizzes").json()["total"] == 0


def test_generate_quiz_ai_failure_returns_502_not_a_fake_quiz(client):
    """Regression test for the original bug: AI failures used to be
    silently stored as a fake quiz. They must now surface as an explicit
    502 and never be persisted."""
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Some Title")),
    ), patch.object(
        __import__("main").quiz_generator,
        "generate_quiz",
        side_effect=QuizGenerationError("model returned garbage"),
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Some_Article"},
        )
    assert r.status_code == 502
    assert client.get("/quizzes").json()["total"] == 0


def test_submit_attempt_scores_correctly(client, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        quiz = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
        ).json()

    # all correct answers are "A" per sample_quiz_output
    r = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["A", "A", "A", "A", "A"], "time_taken": 30},
    )
    assert r.status_code == 200
    assert r.json()["score"] == 100.0

    r2 = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["B", "A", "A", "A", "A"], "time_taken": 30},
    )
    assert r2.json()["score"] == 80.0


def test_submit_attempt_rejects_mismatched_answer_count(client, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        quiz = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
        ).json()

    r = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["A"], "time_taken": 5},
    )
    assert r.status_code == 400


def test_submit_attempt_rejects_too_many_answers(client):
    # MAX_QUIZ_ANSWERS is 20 — this should fail schema validation before
    # ever touching the DB, regardless of whether the quiz exists.
    r = client.post(
        "/quizzes/1/attempt",
        json={"answers": ["A"] * 25, "time_taken": 5},
    )
    assert r.status_code == 422


def test_quiz_history_pagination_and_aggregation(client, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(
            side_effect=[(f"text {i}", f"Title {i}") for i in range(3)]
        ),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        for i in range(3):
            client.post(
                "/generate-quiz",
                json={"url": f"https://en.wikipedia.org/wiki/Article_{i}"},
            )

    r = client.get("/quizzes?limit=2&offset=0")
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2

    r2 = client.get("/quizzes?limit=2&offset=2")
    assert len(r2.json()["items"]) == 1


def test_get_nonexistent_quiz_returns_404(client):
    r = client.get("/quizzes/999999")
    assert r.status_code == 404
