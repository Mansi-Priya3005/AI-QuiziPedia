from pydantic import BaseModel, Field
from typing import List, Dict


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
    key_entities: Dict[str, List[str]] = Field(
        description="Key entities from the article, grouped by category "
        "(e.g. people, organizations, locations)"
    )
    sections: List[str] = Field(description="Main sections of the article")
    quiz: List[QuizQuestion] = Field(
        description="5-8 quiz questions", min_length=5, max_length=8
    )
    related_topics: List[str] = Field(description="Suggested related Wikipedia topics")
