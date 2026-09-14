from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import APIError

from llm_quiz_generator import QuizGenerationError, QuizGenerator, compute_default_question_count
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


@pytest.mark.parametrize(
    "content_length,expected",
    [
        (100, 3),  # tiny content clamps to the minimum, not 0
        (1500, 3),  # still clamps to minimum (1500 // 1500 = 1, below min)
        (7500, 5),  # 7500 // 1500 = 5
        (15000, 10),  # 15000 // 1500 = 10
        (60000, 40),  # would be 40 exactly at the ceiling
        (500000, 40),  # huge document clamps to the maximum, not unbounded
    ],
)
def test_compute_default_question_count_scales_with_length(content_length, expected):
    assert compute_default_question_count(content_length) == expected


def test_generate_quiz_respects_explicit_question_count(generator):
    quiz = _quiz_with_answer("A")  # 5 questions regardless of what's requested
    mock_response = MagicMock()
    mock_response.parsed = quiz

    with patch.object(
        generator.client.models, "generate_content", return_value=mock_response
    ) as mock_call:
        generator.generate_quiz("some text", question_count=20, difficulty="mixed")

    # The prompt sent to the model must reflect the requested count.
    call_kwargs = mock_call.call_args.kwargs
    assert "EXACTLY 20" in call_kwargs["contents"]


def test_generate_quiz_rejects_out_of_range_question_count(generator):
    with pytest.raises(QuizGenerationError, match="between"):
        generator.generate_quiz("text", question_count=1000)


def test_generate_quiz_rejects_invalid_difficulty(generator):
    with pytest.raises(QuizGenerationError, match="Invalid difficulty"):
        generator.generate_quiz("text", difficulty="impossible")


def test_generate_quiz_enforces_requested_difficulty_on_every_question(generator):
    """Even if the model doesn't perfectly follow the difficulty
    instruction, the stored difficulty label must match what was
    requested -- metadata consistency shouldn't depend on the model's
    compliance, same reasoning as the answer-letter normalization."""
    quiz = QuizOutput(
        summary="s",
        key_entities={"people": [], "organizations": [], "locations": []},
        sections=[],
        quiz=[
            QuizQuestion(
                question=f"Q{i}?",
                options=["a", "b", "c", "d"],
                answer="A",
                difficulty="easy",  # model says easy...
                explanation="e",
            )
            for i in range(5)
        ],
        related_topics=[],
    )
    mock_response = MagicMock()
    mock_response.parsed = quiz

    with patch.object(generator.client.models, "generate_content", return_value=mock_response):
        result = generator.generate_quiz("text", difficulty="hard")  # ...but hard was requested

    assert all(q.difficulty == "hard" for q in result.quiz)


def test_generate_quiz_mixed_difficulty_leaves_model_choices_alone(generator):
    quiz = QuizOutput(
        summary="s",
        key_entities={"people": [], "organizations": [], "locations": []},
        sections=[],
        quiz=[
            QuizQuestion(
                question=f"Q{i}?",
                options=["a", "b", "c", "d"],
                answer="A",
                difficulty=d,
                explanation="e",
            )
            for i, d in enumerate(["easy", "medium", "hard", "easy", "medium"])
        ],
        related_topics=[],
    )
    mock_response = MagicMock()
    mock_response.parsed = quiz

    with patch.object(generator.client.models, "generate_content", return_value=mock_response):
        result = generator.generate_quiz("text", difficulty="mixed")

    assert [q.difficulty for q in result.quiz] == ["easy", "medium", "hard", "easy", "medium"]
