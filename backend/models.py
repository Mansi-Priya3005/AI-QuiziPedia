from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class QuizQuestion(BaseModel):
    question: str = Field(description="The quiz question")
    options: List[str] = Field(description="List of 4 options A-D")
    answer: str = Field(description="The correct answer from the options (A, B, C, or D)")
    difficulty: str = Field(description="Difficulty level: easy, medium, or hard")
    explanation: str = Field(description="Short explanation of the answer")

class QuizOutput(BaseModel):
    summary: str = Field(description="Concise summary of the article")
    key_entities: Dict[str, List[str]] = Field(description="Key entities from the article")
    sections: List[str] = Field(description="Main sections of the article")
    quiz: List[QuizQuestion] = Field(description="List of 5-8 quiz questions")
    related_topics: List[str] = Field(description="Suggested related Wikipedia topics")