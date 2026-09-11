from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import APIError

from llm_quiz_generator import QuizGenerationError, QuizGenerator
from models import QuizOutput, QuizQuestion


@pytest.fixture
def generator():
    return QuizGenerator()


def _quiz_with_answer(answer: str) -> QuizOutput:
    """Build a valid 5-question quiz where the first question's answer is
    the one under test (QuizOutput requires 5-8 questions)."""
    questions = [
        QuizQuestion(
            question="Q?",
            options=["a", "b", "c", "d"],
            answer=answer,
            difficulty="easy",
            explanation="e",
        )
    ] + [
        QuizQuestion(
            question=f"Filler {i}?",
            options=["a", "b", "c", "d"],
            answer="A",
            difficulty="easy",
            explanation="e",
        )
        for i in range(4)
    ]
    return QuizOutput(
        summary="s",
        key_entities={"people": [], "organizations": [], "locations": []},
        sections=[],
        quiz=questions,
        related_topics=[],
    )


def test_retryable_error_is_retried_three_times(generator):
    calls = {"n": 0}

    def raise_503(*a, **kw):
        calls["n"] += 1
        raise APIError(503, {"message": "overloaded"})

    with patch.object(generator.client.models, "generate_content", side_effect=raise_503):
        with pytest.raises(QuizGenerationError):
            generator.generate_quiz("article text")

    assert calls["n"] == 3


def test_client_error_is_not_retried(generator):
    calls = {"n": 0}

    def raise_400(*a, **kw):
        calls["n"] += 1
        raise APIError(400, {"message": "bad request"})

    with patch.object(generator.client.models, "generate_content", side_effect=raise_400):
        with pytest.raises(QuizGenerationError):
            generator.generate_quiz("article text")

    assert calls["n"] == 1


def test_happy_path_normalizes_lowercase_answer(generator):
    mock_response = MagicMock()
    mock_response.parsed = _quiz_with_answer("b")

    with patch.object(generator.client.models, "generate_content", return_value=mock_response):
        result = generator.generate_quiz("article text")

    assert result.quiz[0].answer == "B"


def test_unparseable_answer_raises_instead_of_defaulting(generator):
    """Regression test: 'banana'[0].upper() == 'B' must NOT be accepted as
    a valid answer just because its first letter happens to be in A-D."""
    mock_response = MagicMock()
    mock_response.parsed = _quiz_with_answer("banana")

    with patch.object(generator.client.models, "generate_content", return_value=mock_response):
        with pytest.raises(QuizGenerationError, match="unparseable"):
            generator.generate_quiz("article text")


def test_multi_letter_answer_like_ab_is_rejected(generator):
    mock_response = MagicMock()
    mock_response.parsed = _quiz_with_answer("AB")

    with patch.object(generator.client.models, "generate_content", return_value=mock_response):
        with pytest.raises(QuizGenerationError):
            generator.generate_quiz("article text")
