from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
from database import get_db, Quiz, QuizAttempt
from scraper import scrape_wikipedia, validate_wikipedia_url
from llm_quiz_generator import QuizGenerator
import json

app = FastAPI(
    title="AI Wiki Quiz Generator",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000", 
    "http://localhost:5173",
    "https://ai-wiki-quiz-generator-delta.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

quiz_generator = QuizGenerator()

@app.get("/")
def read_root():
    return {"message": "AI Wiki Quiz Generator API"}

@app.post("/generate-quiz", response_model=schemas.QuizResponse)
def generate_quiz(quiz_request: schemas.QuizRequest, db: Session = Depends(get_db)):
    if not validate_wikipedia_url(quiz_request.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Wikipedia URL"
        )
    
    existing_quiz = db.query(Quiz).filter(Quiz.url == quiz_request.url).first()
    if existing_quiz:
        return {
            "id": existing_quiz.id,
            "url": existing_quiz.url,
            "title": existing_quiz.title,
            **existing_quiz.get_quiz_data()
        }
    
    article_text, title = scrape_wikipedia(quiz_request.url)
    if not article_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to scrape Wikipedia article"
        )
    
    quiz_data = quiz_generator.generate_quiz(article_text)
    
    db_quiz = Quiz(
        url=quiz_request.url,
        title=title or "Unknown Title",
        scraped_content=article_text
    )
    db_quiz.set_quiz_data(quiz_data.dict())
    
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    
    return {
        "id": db_quiz.id,
        "url": db_quiz.url,
        "title": db_quiz.title,
        **quiz_data.dict()
    }

@app.post("/quizzes/{quiz_id}/attempt", response_model=schemas.QuizAttemptResponse)
def submit_quiz_attempt(
    quiz_id: int,
    attempt_data: schemas.QuizAttemptCreate,
    db: Session = Depends(get_db)
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    quiz_data = quiz.get_quiz_data()
    quiz_questions = quiz_data.get('quiz', [])
    correct_answers = 0
    user_answers = attempt_data.answers
    
    def is_answer_correct(user_answer, correct_answer, options):
        if not user_answer or not correct_answer:
            return False
        
        if len(correct_answer.strip()) == 1 and correct_answer.strip().upper() in ['A', 'B', 'C', 'D']:
            user_first_char = user_answer.strip()[0].upper() if user_answer else ''
            return user_first_char == correct_answer.strip().upper()
        
        return user_answer.strip() == correct_answer.strip()
    
    for i, question in enumerate(quiz_questions):
        if i < len(user_answers):
            user_answer = user_answers[i]
            correct_answer = question['answer']
            options = question.get('options', [])
            
            if is_answer_correct(user_answer, correct_answer, options):
                correct_answers += 1
    
    total_questions = len(quiz_questions)
    score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    
    attempt = QuizAttempt(
        quiz_id=quiz_id,
        score=score_percentage,
        correct_answers=correct_answers,
        total_questions=total_questions,
        user_answers=user_answers,
        time_taken=attempt_data.time_taken
    )
    
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    
    return {
        "id": attempt.id,
        "score": score_percentage,
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "time_taken": attempt.time_taken,
        "date_attempted": attempt.date_attempted,
        "answers": user_answers
    }

@app.get("/quizzes/{quiz_id}/attempts", response_model=List[schemas.QuizAttemptResponse])
def get_quiz_attempts(
    quiz_id: int,
    db: Session = Depends(get_db)
):
    attempts = db.query(QuizAttempt).filter(
        QuizAttempt.quiz_id == quiz_id
    ).order_by(QuizAttempt.date_attempted.desc()).all()
    
    result = []
    for attempt in attempts:
        user_answers = attempt.user_answers
        if isinstance(user_answers, str):
            try:
                user_answers = json.loads(user_answers)
            except json.JSONDecodeError:
                user_answers = []
        elif not isinstance(user_answers, list):
            user_answers = []
        
        result.append({
            "id": attempt.id,
            "score": float(attempt.score),
            "correct_answers": attempt.correct_answers,
            "total_questions": attempt.total_questions,
            "time_taken": attempt.time_taken,
            "date_attempted": attempt.date_attempted,
            "answers": user_answers
        })
    
    return result

@app.get("/quizzes", response_model=List[schemas.QuizHistory])
def get_quiz_history(db: Session = Depends(get_db)):
    quizzes = db.query(Quiz).order_by(Quiz.date_generated.desc()).all()
    result = []
    
    for quiz in quizzes:
        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).all()
        attempts_count = len(attempts)
        
        best_score = max([attempt.score for attempt in attempts]) if attempts else None
        
        result.append({
            "id": quiz.id,
            "url": quiz.url,
            "title": quiz.title,
            "date_generated": quiz.date_generated,
            "attempts_count": attempts_count,
            "best_score": best_score
        })
    
    return result

@app.get("/quizzes/{quiz_id}", response_model=schemas.QuizResponse)
def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    quiz_data = quiz.get_quiz_data()
    return {
        "id": quiz.id,
        "url": quiz.url,
        "title": quiz.title,
        "summary": quiz_data.get('summary', ''),
        "key_entities": quiz_data.get('key_entities', {}),
        "sections": quiz_data.get('sections', []),
        "quiz": quiz_data.get('quiz', []),
        "related_topics": quiz_data.get('related_topics', [])
    }

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {
            "status": "healthy", 
            "message": "API and database are running",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": "Database connection failed",
            "error": str(e)
        }

@app.get("/endpoints")
def list_endpoints():
    endpoints = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            endpoints.append({
                "path": route.path,
                "methods": list(route.methods)
            })
    return endpoints