from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answer: str
    difficulty: str
    explanation: str

class QuizRequest(BaseModel):
    url: str

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

class QuizAttemptCreate(BaseModel):
    answers: List[str]
    time_taken: int

class QuizAttemptResponse(BaseModel):
    id: int
    score: float
    correct_answers: int
    total_questions: int
    time_taken: int
    date_attempted: datetime
    answers: List[str]