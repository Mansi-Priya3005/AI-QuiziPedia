import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

WIKIPEDIA_URL_PATTERN = re.compile(r"^https://([a-z]{2,12}\.)?wikipedia\.org/wiki/.+")

# These bounds exist because the previous version trusted the client's
# answers/time_taken completely: a client could submit 10,000 answers for
# a 5-question quiz, or a negative/absurd time_taken, and it would be
# stored as-is.
MAX_QUIZ_ANSWERS = 20
MAX_TIME_TAKEN_SECONDS = 24 * 60 * 60  # 1 day — generous upper bound


class QuizQuestion(BaseModel):
    question: str
    options: List[str] = Field(min_length=2, max_length=6)
    answer: str
    difficulty: str
    explanation: str


class QuizRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def must_be_wikipedia_url(cls, v: str) -> str:
        if not WIKIPEDIA_URL_PATTERN.match(v):
            raise ValueError("url must be a valid Wikipedia article URL")
        return v


class QuizResponse(BaseModel):
    id: int
    url: str
    title: str
    summary: str
    key_entities: dict
    sections: List[str]
    quiz: List[QuizQuestion]
    related_topics: List[str]


class QuizHistory(BaseModel):
    id: int
    url: str
    title: str
    date_generated: datetime
    attempts_count: int
    best_score: Optional[float] = None


class PaginatedQuizHistory(BaseModel):
    items: List[QuizHistory]
    total: int
    limit: int
    offset: int


class QuizAttemptCreate(BaseModel):
    answers: List[str] = Field(max_length=MAX_QUIZ_ANSWERS)
    time_taken: int = Field(ge=0, le=MAX_TIME_TAKEN_SECONDS)


class QuizAttemptResponse(BaseModel):
    id: int
    score: float
    correct_answers: int
    total_questions: int
    time_taken: int
    date_attempted: datetime
    answers: List[str]
