import logging

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

MODEL_NAME = "gemini-2.5-flash"
MAX_ARTICLE_CHARS = 12000  # ~ a few thousand tokens, well within context


class QuizGenerationError(Exception):
    """Raised when quiz generation fails after retries.

    The caller (main.py) is expected to turn this into an explicit 502/503
    response. We deliberately do NOT swallow this into a fake placeholder
    quiz — a silently-stored "the AI failed" quiz is worse than a clear
    error, because it looks like real content in quiz history.
    """


PROMPT_TEMPLATE = """You are an expert educational content creator. Create a \
comprehensive quiz based on the following Wikipedia article content.

ARTICLE CONTENT:
{article_text}

INSTRUCTIONS:
1. Generate 5-8 high-quality quiz questions that test understanding of key concepts.
2. Questions must be factual and directly answerable from the provided content only.
3. Each question must have exactly 4 options.
4. The "answer" field must contain ONLY the letter A, B, C, or D — never the option text.
5. Assign a difficulty level (easy, medium, or hard) per question.
6. Provide a brief explanation for each answer, grounded in the article text.
7. Extract key entities (people, organizations, locations) mentioned in the article.
8. Identify the main sections/topics covered by the article.
9. Suggest 3-5 related Wikipedia topics for further reading.
"""


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
    def _call_model(self, article_text: str):
        prompt = PROMPT_TEMPLATE.format(article_text=article_text[:MAX_ARTICLE_CHARS])
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

    def generate_quiz(self, article_text: str) -> QuizOutput:
        """Generate a quiz from article text using structured Gemini output.

        Raises QuizGenerationError on any failure (network, API, or
        validation) after retries are exhausted. Callers must handle this
        explicitly rather than receiving a fake "quiz" that just describes
        the failure.
        """
        try:
            response = self._call_model(article_text)
        except APIError as e:
            logger.error("Gemini API error during quiz generation: %s", e)
            raise QuizGenerationError(f"AI generation failed: {e}") from e
        except Exception as e:  # network errors, timeouts, etc.
            logger.error("Unexpected error calling Gemini: %s", e)
            raise QuizGenerationError(f"AI generation failed: {e}") from e

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, QuizOutput):
            quiz_data = parsed
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

        self._normalize_answers(quiz_data)
        return quiz_data

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
