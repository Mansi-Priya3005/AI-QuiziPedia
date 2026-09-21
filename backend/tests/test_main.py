from unittest.mock import AsyncMock, patch

import pytest

from llm_quiz_generator import QuizGenerationError, QuotaExceededError
from scraper import ScrapeError
from web_extractor import FetchedContent


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200


def test_health_check_reports_db_connected(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_generate_quiz_requires_auth(client):
    r = client.post(
        "/generate-quiz", json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"}
    )
    assert r.status_code == 401


def test_quizzes_list_requires_auth(client):
    r = client.get("/quizzes")
    assert r.status_code == 401


@pytest.mark.parametrize(
    "bad_url", ["not a url at all", "ftp://example.com/file.txt", "javascript:alert(1)", "file:///etc/passwd"]
)
def test_generate_quiz_rejects_non_http_url(client, auth_headers, bad_url):
    r = client.post("/generate-quiz", json={"url": bad_url}, headers=auth_headers)
    assert r.status_code == 422


def test_generate_quiz_accepts_non_wikipedia_url(client, auth_headers, sample_quiz_output):
    """Any http(s) link is accepted now, not just Wikipedia -- non-Wikipedia
    links go through the generic fetcher and are stored with its source_type."""
    with patch(
        "main.fetch_url_content",
        new=AsyncMock(
            return_value=FetchedContent(
                text="blog post text", title="My Blog Post", source_type="web"
            )
        ),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://example.com/blog/my-post"},
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "My Blog Post"
    assert body["source_type"] == "web"
    assert body["url"] == "https://example.com/blog/my-post"


def test_generate_quiz_google_doc_source_type(client, auth_headers, sample_quiz_output):
    with patch(
        "main.fetch_url_content",
        new=AsyncMock(
            return_value=FetchedContent(
                text="notes", title="Lecture Notes", source_type="google_doc"
            )
        ),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://docs.google.com/document/d/abc123DEF456/edit"},
            headers=auth_headers,
        )
    assert r.status_code == 200
    assert r.json()["source_type"] == "google_doc"


def test_generate_quiz_fetch_failure_returns_400(client, auth_headers):
    with patch(
        "main.fetch_url_content",
        new=AsyncMock(side_effect=ScrapeError("That page couldn't be found (HTTP 404).")),
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://example.com/missing"},
            headers=auth_headers,
        )
    assert r.status_code == 400
    assert "404" in r.json()["detail"]


def test_generate_quiz_happy_path(client, auth_headers, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Ada Lovelace"
    assert len(body["quiz"]) == 5


def test_generate_quiz_deduplicates_same_url_for_same_user(client, auth_headers, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r1 = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=auth_headers,
        )
        r2 = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=auth_headers,
        )
    assert r1.json()["id"] == r2.json()["id"]


def test_two_users_get_separate_quizzes_for_same_url(client, sample_quiz_output):
    """Each user gets their own copy of a quiz, not a shared global one."""
    user_a = client.post(
        "/auth/signup", json={"email": "alice@example.com", "password": "password123"}
    ).json()
    user_b = client.post(
        "/auth/signup", json={"email": "bob@example.com", "password": "password123"}
    ).json()
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r_a = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=headers_a,
        )
        r_b = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=headers_b,
        )

    assert r_a.json()["id"] != r_b.json()["id"]

    # And neither user can see the other's quiz by id
    assert client.get(f"/quizzes/{r_a.json()['id']}", headers=headers_b).status_code == 404
    assert client.get(f"/quizzes/{r_b.json()['id']}", headers=headers_a).status_code == 404


def test_generate_quiz_scrape_failure_returns_400_and_stores_nothing(client, auth_headers):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(side_effect=ScrapeError("That Wikipedia page doesn't exist.")),
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Nonexistent_Xyz"},
            headers=auth_headers,
        )
    assert r.status_code == 400
    assert client.get("/quizzes", headers=auth_headers).json()["total"] == 0


def test_generate_quiz_ai_failure_returns_502_not_a_fake_quiz(client, auth_headers):
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
            headers=auth_headers,
        )
    assert r.status_code == 502
    assert client.get("/quizzes", headers=auth_headers).json()["total"] == 0


def test_submit_attempt_scores_correctly(client, auth_headers, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        quiz = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=auth_headers,
        ).json()

    # Correct answer for every question is "A" per sample_quiz_output, but
    # the real frontend submits the full option TEXT the user clicked
    # (see QuizTaker's handleAnswerSelect), not the bare letter -- so the
    # realistic correct submission for option A is "A) opt1", not "A".
    r = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["A) opt1"] * 5, "time_taken": 30},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["score"] == 100.0

    r2 = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["B) opt2"] + ["A) opt1"] * 4, "time_taken": 30},
        headers=auth_headers,
    )
    assert r2.json()["score"] == 80.0


def test_scoring_matches_real_frontend_behavior_option_text_without_letter_prefix(
    client, auth_headers
):
    """Regression test for a real reported bug: scores always came out
    near 0% regardless of what the user actually selected. Root cause:
    the frontend stores the full option TEXT the user clicked (not a
    bare letter), but scoring compared user_answer's first CHARACTER
    against the correct letter -- which only ever matched by coincidence
    when an option's text happened to start with its own letter.

    The existing scoring test used options like "A) opt1" (which starts
    with its own letter) and submitted bare letters like "A" as the
    answer, both of which accidentally satisfied the old broken logic.
    This test uses option text with no letter prefix at all -- the
    realistic shape of real Gemini output -- to actually catch this
    class of bug.
    """
    from models import QuizOutput, QuizQuestion

    quiz_output = QuizOutput(
        summary="s",
        key_entities={"people": [], "organizations": [], "locations": []},
        sections=[],
        quiz=[
            QuizQuestion(
                question="What is the capital of France?",
                options=["Paris", "London", "Berlin", "Madrid"],
                answer="A",  # "Paris" is correct, and does NOT start with "A"
                difficulty="easy",
                explanation="Paris is the capital of France.",
            ),
            QuizQuestion(
                question="What is the capital of the UK?",
                options=["Paris", "London", "Berlin", "Madrid"],
                answer="B",  # "London" is correct, does NOT start with "B"
                difficulty="easy",
                explanation="London is the capital of the UK.",
            ),
        ],
        related_topics=[],
    )

    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Geography")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=quiz_output
    ):
        quiz = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Geography"},
            headers=auth_headers,
        ).json()

    # Submit exactly what the real frontend sends: the full option TEXT
    # the user clicked, for the objectively correct answer to both
    # questions ("Paris" and "London").
    r = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["Paris", "London"], "time_taken": 30},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 100.0, (
        f"Expected 100% for objectively correct answers, got {body['score']}% "
        "-- scoring is comparing against the wrong thing"
    )
    assert body["correct_answers"] == 2

    # And a genuinely wrong answer must still score as wrong.
    r2 = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["Berlin", "Madrid"], "time_taken": 30},
        headers=auth_headers,
    )
    assert r2.json()["score"] == 0.0


def test_cannot_submit_attempt_on_another_users_quiz(client, sample_quiz_output):
    owner = client.post(
        "/auth/signup", json={"email": "owner@example.com", "password": "password123"}
    ).json()
    intruder = client.post(
        "/auth/signup", json={"email": "intruder@example.com", "password": "password123"}
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    intruder_headers = {"Authorization": f"Bearer {intruder['access_token']}"}

    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        quiz = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=owner_headers,
        ).json()

    r = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["A", "A", "A", "A", "A"], "time_taken": 30},
        headers=intruder_headers,
    )
    assert r.status_code == 404


def test_submit_attempt_rejects_mismatched_answer_count(client, auth_headers, sample_quiz_output):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        quiz = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=auth_headers,
        ).json()

    r = client.post(
        f"/quizzes/{quiz['id']}/attempt",
        json={"answers": ["A"], "time_taken": 5},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_submit_attempt_rejects_too_many_answers(client, auth_headers):
    # MAX_QUIZ_ANSWERS is 20 — this should fail schema validation before
    # ever touching the DB, regardless of whether the quiz exists.
    r = client.post(
        "/quizzes/1/attempt",
        json={"answers": ["A"] * 25, "time_taken": 5},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_quiz_history_pagination_and_aggregation(client, auth_headers, sample_quiz_output):
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
                headers=auth_headers,
            )

    r = client.get("/quizzes?limit=2&offset=0", headers=auth_headers)
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2

    r2 = client.get("/quizzes?limit=2&offset=2", headers=auth_headers)
    assert len(r2.json()["items"]) == 1


def test_quiz_history_only_shows_own_quizzes(client, sample_quiz_output):
    user_a = client.post(
        "/auth/signup", json={"email": "alice2@example.com", "password": "password123"}
    ).json()
    user_b = client.post(
        "/auth/signup", json={"email": "bob2@example.com", "password": "password123"}
    ).json()
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Some Article")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Some_Article"},
            headers=headers_a,
        )

    assert client.get("/quizzes", headers=headers_a).json()["total"] == 1
    assert client.get("/quizzes", headers=headers_b).json()["total"] == 0


def test_get_nonexistent_quiz_returns_404(client, auth_headers):
    r = client.get("/quizzes/999999", headers=auth_headers)
    assert r.status_code == 404


def test_generate_quiz_from_file_requires_auth(client):
    r = client.post(
        "/generate-quiz-from-file",
        files={"file": ("notes.txt", b"some content", "text/plain")},
    )
    assert r.status_code == 401


def test_generate_quiz_from_text_file_happy_path(client, auth_headers, sample_quiz_output):
    with patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r = client.post(
            "/generate-quiz-from-file",
            files={"file": ("notes.txt", b"Photosynthesis converts light into energy.", "text/plain")},
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] == "upload"
    assert body["url"] is None
    assert body["title"] == "notes.txt"


def test_generate_quiz_from_file_rejects_unsupported_type(client, auth_headers):
    r = client.post(
        "/generate-quiz-from-file",
        files={"file": ("image.png", b"fake-image-bytes", "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


def test_generate_quiz_from_file_ai_failure_returns_502(client, auth_headers):
    with patch.object(
        __import__("main").quiz_generator,
        "generate_quiz",
        side_effect=QuizGenerationError("model failed"),
    ):
        r = client.post(
            "/generate-quiz-from-file",
            files={"file": ("notes.txt", b"Some study notes content here.", "text/plain")},
            headers=auth_headers,
        )
    assert r.status_code == 502
    assert client.get("/quizzes", headers=auth_headers).json()["total"] == 0


def test_multiple_uploads_do_not_collide(client, auth_headers, sample_quiz_output):
    """Unlike Wikipedia URLs, uploads have no dedup key -- each upload
    creates its own quiz even with the same filename."""
    with patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r1 = client.post(
            "/generate-quiz-from-file",
            files={"file": ("notes.txt", b"First set of notes.", "text/plain")},
            headers=auth_headers,
        )
        r2 = client.post(
            "/generate-quiz-from-file",
            files={"file": ("notes.txt", b"Second set of notes.", "text/plain")},
            headers=auth_headers,
        )
    assert r1.json()["id"] != r2.json()["id"]
    assert client.get("/quizzes", headers=auth_headers).json()["total"] == 2


def test_same_url_different_question_count_creates_separate_quizzes(
    client, auth_headers, sample_quiz_output
):
    """Regression test: dedup must key on the REQUESTED settings, not the
    resolved/actual count -- otherwise a second request with explicit
    settings either silently returns the wrong quiz or hits a spurious
    409 (both happened during development of this feature)."""
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ):
        r1 = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace", "question_count": 10},
            headers=auth_headers,
        )
        r2 = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace", "question_count": 20},
            headers=auth_headers,
        )
        # Same URL, same (default) settings as r1's implicit None -- should
        # NOT collide with r1's explicit 10, since None != 10.
        r3 = client.post(
            "/generate-quiz",
            json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace"},
            headers=auth_headers,
        )

    ids = {r1.json()["id"], r2.json()["id"], r3.json()["id"]}
    assert len(ids) == 3
    assert client.get("/quizzes", headers=auth_headers).json()["total"] == 3


def test_generate_quiz_passes_question_count_and_difficulty_to_generator(
    client, auth_headers, sample_quiz_output
):
    with patch(
        "main.scrape_wikipedia",
        new=AsyncMock(return_value=("article text", "Ada Lovelace")),
    ), patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ) as mock_generate:
        client.post(
            "/generate-quiz",
            json={
                "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
                "question_count": 15,
                "difficulty": "hard",
            },
            headers=auth_headers,
        )

    mock_generate.assert_called_once_with(
        "article text", question_count=15, difficulty="hard"
    )


def test_generate_quiz_rejects_invalid_difficulty(client, auth_headers):
    r = client.post(
        "/generate-quiz",
        json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace", "difficulty": "impossible"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_generate_quiz_rejects_out_of_range_question_count(client, auth_headers):
    r = client.post(
        "/generate-quiz",
        json={"url": "https://en.wikipedia.org/wiki/Ada_Lovelace", "question_count": 999},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_generate_quiz_from_file_passes_question_count_and_difficulty(
    client, auth_headers, sample_quiz_output
):
    with patch.object(
        __import__("main").quiz_generator, "generate_quiz", return_value=sample_quiz_output
    ) as mock_generate:
        client.post(
            "/generate-quiz-from-file",
            files={"file": ("notes.txt", b"Some study notes.", "text/plain")},
            data={"question_count": "12", "difficulty": "easy"},
            headers=auth_headers,
        )

    mock_generate.assert_called_once_with(
        "Some study notes.", question_count=12, difficulty="easy"
    )


def test_generate_quiz_quota_exceeded_returns_429_with_clear_message(client, auth_headers):
    with patch(
        "main.fetch_url_content",
        new=AsyncMock(
            return_value=FetchedContent(text="text", title="T", source_type="web")
        ),
    ), patch.object(
        __import__("main").quiz_generator,
        "generate_quiz",
        side_effect=QuotaExceededError("quota"),
    ):
        r = client.post(
            "/generate-quiz",
            json={"url": "https://example.com/post"},
            headers=auth_headers,
        )
    assert r.status_code == 429
    assert "usage limit" in r.json()["detail"]
    assert client.get("/quizzes", headers=auth_headers).json()["total"] == 0
