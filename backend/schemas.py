from datetime import datetime
from urllib.parse import urlparse
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

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


DIFFICULTY_OPTIONS = ("easy", "medium", "hard", "mixed")
MIN_QUESTION_COUNT = 3
MAX_QUESTION_COUNT = 40


class QuizRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    question_count: Optional[int] = Field(
        default=None, ge=MIN_QUESTION_COUNT, le=MAX_QUESTION_COUNT
    )
    difficulty: str = Field(default="mixed")

    @field_validator("url")
    @classmethod
    def must_be_http_url(cls, v: str) -> str:
        # Shape check only (http/https + a host). Whether the link is
        # actually fetchable -- and safe to fetch, i.e. not pointing at
        # the server's own internal network -- is enforced in
        # web_extractor, which has to re-check on every redirect anyway.
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("url must be a valid http(s) link")
        return v

    @field_validator("difficulty")
    @classmethod
    def must_be_valid_difficulty(cls, v: str) -> str:
        if v not in DIFFICULTY_OPTIONS:
            raise ValueError(f"difficulty must be one of {DIFFICULTY_OPTIONS}")
        return v


class QuizResponse(BaseModel):
    id: int
    url: Optional[str] = None
    source_type: str = "wikipedia"
    question_count: Optional[int] = None
    difficulty: Optional[str] = None
    title: str
    summary: str
    key_entities: dict
    sections: List[str]
    quiz: List[QuizQuestion]
    related_topics: List[str]


class QuizHistory(BaseModel):
    id: int
    url: Optional[str] = None
    source_type: str = "wikipedia"
    question_count: Optional[int] = None
    difficulty: Optional[str] = None
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


class UserSignup(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    # bcrypt silently truncates/ignores bytes beyond 72 -- capping the
    # input length here means what the user typed is actually what gets
    # checked, rather than a password that "works" up to 72 characters
    # and silently stops mattering after that.
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def basic_email_shape(cls, v: str) -> str:
        # Deliberately not a full RFC 5322 validator -- just enough to
        # catch obvious typos ("not an email") without rejecting valid
        # addresses that stricter regexes often get wrong.
        if "@" not in v or " " in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("must be a valid email address")
        return v.lower().strip()


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
