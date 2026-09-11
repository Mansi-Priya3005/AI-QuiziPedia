from pydantic import BaseModel, Field
from typing import List


class KeyEntities(BaseModel):
    """Fixed-shape entity groups.

    Deliberately NOT a Dict[str, List[str]] (open/arbitrary-keys mapping):
    Pydantic converts an open dict into a JSON Schema using
    'additionalProperties', which the public Gemini Developer API rejects
    in structured-output mode ("additionalProperties is only supported in
    Gemini Enterprise Agent Platform mode"). A fixed set of named fields
    produces a schema Gemini's structured output actually accepts.
    """

    people: List[str] = Field(default_factory=list, description="People mentioned in the article")
    organizations: List[str] = Field(
        default_factory=list, description="Organizations mentioned in the article"
    )
    locations: List[str] = Field(
        default_factory=list, description="Locations mentioned in the article"
    )


class QuizQuestion(BaseModel):
    question: str = Field(description="The quiz question")
    options: List[str] = Field(
        description="Exactly 4 answer options", min_length=4, max_length=4
    )
    answer: str = Field(description="The correct answer letter: A, B, C, or D")
    difficulty: str = Field(description="Difficulty level: easy, medium, or hard")
    explanation: str = Field(description="Short explanation of the answer")


class QuizOutput(BaseModel):
    summary: str = Field(description="Concise summary of the article")
    key_entities: KeyEntities = Field(
        description="Key entities from the article, grouped into people, organizations, and locations"
    )
    sections: List[str] = Field(description="Main sections of the article")
    quiz: List[QuizQuestion] = Field(
        description="5-8 quiz questions", min_length=5, max_length=8
    )
    related_topics: List[str] = Field(description="Suggested related Wikipedia topics")
