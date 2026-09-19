import logging
from typing import Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from models import QuizOutput

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.6-flash"

# gemini-3.6-flash has a 1,048,576 token context window (~4 chars/token is
# a reasonable rule of thumb for English text), so a 12,000-character cap
# was using well under 1% of what's actually available -- that was the
# root cause of large documents (e.g. a 48-page PDF) getting truncated to
# a handful of pages before the model ever saw the rest. This is set well
# below the real limit to leave headroom for the prompt/schema overhead
# and the model's own output tokens, while covering the vast majority of
# real documents (this is roughly 150-200 pages of text) in full.
MAX_ARTICLE_CHARS = 400_000

MIN_QUESTIONS = 3
MAX_QUESTIONS = 40
DIFFICULTIES = ("easy", "medium", "hard", "mixed")


class QuizGenerationError(Exception):
    """Raised when quiz generation fails after retries.

    The caller (main.py) is expected to turn this into an explicit 502/503
    response. We deliberately do NOT swallow this into a fake placeholder
    quiz — a silently-stored "the AI failed" quiz is worse than a clear
    error, because it looks like real content in quiz history.
    """


def compute_default_question_count(content_length: int) -> int:
    """Scale the target question count to how much source content there
    actually is, instead of a fixed 5-8 regardless of whether the source
    is a paragraph or a 48-page document. Roughly one question per 1,500
    characters of source text, bounded to a sane range."""
    estimated = content_length // 1500
    return max(MIN_QUESTIONS, min(MAX_QUESTIONS, estimated))


PROMPT_TEMPLATE = """You are an expert educational content creator. Create a \
comprehensive quiz based on the following source content.

SOURCE CONTENT:
{article_text}

INSTRUCTIONS:
1. Generate EXACTLY {question_count} high-quality quiz questions that test \
understanding of key concepts. Draw questions from across the ENTIRE source \
content provided, not just the beginning -- if the content covers many \
distinct topics or sections, distribute questions across all of them rather \
than clustering on the first few.
2. Questions must be factual and directly answerable from the provided content only.
3. Each question must have exactly 4 options.
4. The "answer" field must contain ONLY the letter A, B, C, or D — never the option text.
5. {difficulty_instruction}
6. Provide a brief explanation for each answer, grounded in the source content.
7. Extract key entities (people, organizations, locations) mentioned in the content.
8. Identify the main sections/topics covered by the content.
9. Suggest 3-5 related topics for further reading.
"""

DIFFICULTY_INSTRUCTIONS = {
    "mixed": "Assign a difficulty level (easy, medium, or hard) per question, "
    "with a reasonable mix across the quiz.",
    "easy": "Every question must be easy difficulty -- straightforward recall "
    "of explicitly stated facts.",
    "medium": "Every question must be medium difficulty -- requires connecting "
    "two or more pieces of information from the content.",
    "hard": "Every question must be hard difficulty -- requires deeper "
    "understanding, inference, or synthesis across the content, not just recall.",
}


def _is_retryable_api_error(exc: BaseException) -> bool:
    """Only retry on transient failures (rate limit / server errors), not
    on 4xx client errors like a bad request or invalid API key, which will
    never succeed no matter how many times we retry."""
    if not isinstance(exc, APIError):
        return False
    return exc.code in (429, 500, 502, 503, 504)


class QuizGenerator:
    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        self.client = genai.Client(api_key=settings.gemini_api_key)

    @retry(
        retry=retry_if_exception(_is_retryable_api_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _call_model(self, article_text: str, question_count: int, difficulty: str):
        prompt = PROMPT_TEMPLATE.format(
            article_text=article_text[:MAX_ARTICLE_CHARS],
            question_count=question_count,
            difficulty_instruction=DIFFICULTY_INSTRUCTIONS[difficulty],
        )
        return self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                # Structured output: Gemini enforces this JSON Schema itself,
                # replacing the old "hope the model formats it right, then
                # regex-strip markdown fences and hope json.loads doesn't
                # throw" approach.
                response_schema=QuizOutput,
                temperature=0.4,
            ),
        )

    def generate_quiz(
        self,
        article_text: str,
        question_count: Optional[int] = None,
        difficulty: str = "mixed",
    ) -> QuizOutput:
        """Generate a quiz from article text using structured Gemini output.

        question_count: exact number of questions to request. If None,
        scales automatically with content length (see
        compute_default_question_count).
        difficulty: "easy" | "medium" | "hard" | "mixed" (default).

        Raises QuizGenerationError on any failure (network, API, or
        validation) after retries are exhausted, or on invalid arguments.
        Callers must handle this explicitly rather than receiving a fake
        "quiz" that just describes the failure.
        """
        if difficulty not in DIFFICULTIES:
            raise QuizGenerationError(
                f"Invalid difficulty {difficulty!r}, must be one of {DIFFICULTIES}"
            )

        if question_count is None:
            question_count = compute_default_question_count(len(article_text))
        elif not (MIN_QUESTIONS <= question_count <= MAX_QUESTIONS):
            raise QuizGenerationError(
                f"question_count must be between {MIN_QUESTIONS} and {MAX_QUESTIONS}"
            )

        try:
            response = self._call_model(article_text, question_count, difficulty)
        except APIError as e:
            logger.error("Gemini API error during quiz generation: %s", e)
            raise QuizGenerationError(f"AI generation failed: {e}") from e
        except Exception as e:  # network errors, timeouts, etc.
            logger.error("Unexpected error calling Gemini: %s", e)
            raise QuizGenerationError(f"AI generation failed: {e}") from e

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, QuizOutput):
            quiz_data = parsed
        elif not getattr(response, "text", None):
            # No parsed object AND no text means the model produced no
            # content at all -- this is a different failure mode from "the
            # model's output didn't match our schema", and deserves a
            # different, honest message. Common causes: the prompt or
            # response was blocked by safety filters (sensitive source
            # material -- e.g. a Wikipedia article or document with graphic
            # or disturbing content), or the response was cut off before
            # any content was produced.
            reason = self._describe_empty_response(response)
            logger.error("Gemini returned no content: %s", reason)
            raise QuizGenerationError(
                f"The AI declined to generate a quiz for this content ({reason}). "
                "Try a different source, or a lower question count."
            )
        else:
            # Fall back to manual parse if the SDK didn't attach .parsed
            # (e.g. schema mismatch) — still validated by Pydantic, still
            # raises rather than silently substituting content.
            try:
                quiz_data = QuizOutput.model_validate_json(response.text)
            except (ValidationError, ValueError) as e:
                logger.error("Gemini response failed schema validation: %s", e)
                raise QuizGenerationError(
                    "AI returned a response that didn't match the expected quiz format"
                ) from e

        self._validate_shape(quiz_data)
        self._normalize_answers(quiz_data)
        if difficulty != "mixed":
            self._enforce_difficulty(quiz_data, difficulty)
        return quiz_data

    @staticmethod
    def _validate_shape(quiz_data: QuizOutput) -> None:
        """Enforces constraints that used to live in the schema sent to
        Gemini (exactly 4 options per question, at least one question) --
        moved here in Python because a response_schema with array-length
        constraints (minItems/maxItems) is a documented cause of Gemini
        returning a 400 INVALID_ARGUMENT on otherwise-valid requests. See
        MAX_ARTICLE_CHARS comment history / commit log for the incident
        this fixed."""
        if not quiz_data.quiz:
            raise QuizGenerationError("AI generated zero questions")
        for i, question in enumerate(quiz_data.quiz):
            if len(question.options) != 4:
                raise QuizGenerationError(
                    f"Question {i + 1} has {len(question.options)} options, expected exactly 4"
                )

    @staticmethod
    def _describe_empty_response(response) -> str:
        """Best-effort human-readable reason the model returned no
        content, using whatever the API told us. Never raises -- this is
        purely for a clearer error message, so a malformed/unexpected
        response shape here must not itself crash the request."""
        try:
            prompt_feedback = getattr(response, "prompt_feedback", None)
            if prompt_feedback and getattr(prompt_feedback, "block_reason", None):
                return f"blocked: {prompt_feedback.block_reason}"

            candidates = getattr(response, "candidates", None) or []
            if candidates:
                finish_reason = getattr(candidates[0], "finish_reason", None)
                if finish_reason:
                    return f"finish reason: {finish_reason}"
        except Exception:
            pass
        return "no reason given by the API"

    @staticmethod
    def _normalize_answers(quiz_data: QuizOutput) -> None:
        """Normalize answer letters defensively, but never invent a wrong
        answer — an unparseable answer is a generation failure, not a
        default to option 'A' (the previous behavior silently produced
        wrong answer keys).

        Must require the WHOLE trimmed answer to be a single A-D letter,
        not just start with one — 'banana'[0].upper() == 'B' would
        otherwise silently pass as answer 'B', which is exactly the kind
        of prefix-match bug the original code had with its regex."""
        for question in quiz_data.quiz:
            answer = question.answer.strip().upper()
            if len(answer) == 1 and answer in ("A", "B", "C", "D"):
                question.answer = answer
            else:
                raise QuizGenerationError(
                    f"AI produced an unparseable answer key: {question.answer!r}"
                )

    @staticmethod
    def _enforce_difficulty(quiz_data: QuizOutput, difficulty: str) -> None:
        """The prompt asks the model to label every question with the
        requested difficulty, but metadata consistency shouldn't depend on
        the model following instructions perfectly -- enforce it directly
        rather than trusting free-form compliance, same reasoning as the
        answer-letter normalization above."""
        for question in quiz_data.quiz:
            question.difficulty = difficulty
