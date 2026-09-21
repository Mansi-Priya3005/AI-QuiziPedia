import json
import logging

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional

import schemas
from auth import create_access_token, get_current_user, hash_password, verify_password
from config import settings
from database import Quiz, QuizAttempt, User, get_db
from document_extractor import DocumentExtractionError, extract_text_from_upload
from llm_quiz_generator import QuizGenerationError, QuizGenerator
from scraper import ScrapeError, scrape_wikipedia, validate_wikipedia_url
from web_extractor import fetch_url_content

logging.basicConfig(
    level=logging.INFO if settings.is_production else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AI Wiki Quiz Generator",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS origins are environment-driven (CORS_ALLOWED_ORIGINS), not
# hardcoded — a hardcoded allowlist meant every new deploy target required
# a code change and redeploy just to update it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

quiz_generator = QuizGenerator()


def _quiz_to_response_dict(quiz: Quiz) -> dict:
    quiz_data = quiz.get_quiz_data()
    return {
        "id": quiz.id,
        "url": quiz.url,
        "source_type": quiz.source_type,
        "question_count": quiz.question_count,
        "difficulty": quiz.difficulty,
        "title": quiz.title,
        "summary": quiz_data.get("summary", ""),
        "key_entities": quiz_data.get("key_entities", {}),
        "sections": quiz_data.get("sections", []),
        "quiz": quiz_data.get("quiz", []),
        "related_topics": quiz_data.get("related_topics", []),
    }


async def _load_source_from_url(url: str):
    """Returns (text, title, source_type) for any supported link.

    Wikipedia keeps its dedicated MediaWiki-API path (cleaner and more
    reliable than scraping rendered HTML); every other link -- web pages,
    Google Docs/Slides, Drive files, hosted PDFs -- goes through the
    generic fetcher. Raises ScrapeError with a user-facing reason.
    """
    if validate_wikipedia_url(url):
        text, title = await scrape_wikipedia(url)
        return text, title, "wikipedia"
    fetched = await fetch_url_content(url)
    return fetched.text, fetched.title, fetched.source_type


@app.get("/")
def read_root():
    return {"message": "AI Wiki Quiz Generator API"}


@app.post("/auth/signup", response_model=schemas.Token, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.auth_rate_limit)
def signup(request: Request, signup_data: schemas.UserSignup, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == signup_data.email).first()
    if existing:
        # Deliberately vague rather than "email already registered" --
        # confirming which emails have accounts is a minor enumeration
        # leak best avoided even for a portfolio-scale app.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create account with these details",
        )

    user = User(email=signup_data.email, hashed_password=hash_password(signup_data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create account with these details",
        )
    db.refresh(user)

    token = create_access_token(user.id)
    return {"access_token": token, "user": user}


@app.post("/auth/login", response_model=schemas.Token)
@limiter.limit(settings.auth_rate_limit)
def login(request: Request, login_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email.lower().strip()).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(user.id)
    return {"access_token": token, "user": user}


@app.get("/auth/me", response_model=schemas.UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/generate-quiz", response_model=schemas.QuizResponse)
@limiter.limit(settings.generate_quiz_rate_limit)
async def generate_quiz(
    request: Request,  # required by slowapi's limiter decorator
    quiz_request: schemas.QuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dedup_filters = [
        Quiz.url == quiz_request.url,
        Quiz.owner_id == current_user.id,
        Quiz.question_count == quiz_request.question_count,
        Quiz.difficulty == quiz_request.difficulty,
    ]
    existing_quiz = db.query(Quiz).filter(*dedup_filters).first()
    if existing_quiz:
        return _quiz_to_response_dict(existing_quiz)

    try:
        article_text, title, source_type = await _load_source_from_url(quiz_request.url)
    except ScrapeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        quiz_data = quiz_generator.generate_quiz(
            article_text,
            question_count=quiz_request.question_count,
            difficulty=quiz_request.difficulty,
        )
    except QuizGenerationError as e:
        # Explicit 502 (upstream/AI failure) instead of silently storing a
        # fallback quiz that looks like real content in quiz history.
        logger.error("Quiz generation failed for %s: %s", quiz_request.url, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service failed to generate a quiz for this content. Please try again.",
        )

    db_quiz = Quiz(
        owner_id=current_user.id,
        url=quiz_request.url,
        source_type=source_type,
        question_count=quiz_request.question_count,
        difficulty=quiz_request.difficulty,
        title=title or "Unknown Title",
        scraped_content=article_text,
    )
    db_quiz.set_quiz_data(quiz_data.model_dump())

    db.add(db_quiz)
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent requests for the same (user, URL, settings)
        # combination can both pass the existing_quiz check above and
        # both try to insert — the unique constraint is the real guard,
        # this just turns the resulting race into "return the quiz the
        # other request created" instead of a raw 500.
        db.rollback()
        existing_quiz = db.query(Quiz).filter(*dedup_filters).first()
        if existing_quiz:
            return _quiz_to_response_dict(existing_quiz)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A quiz for this URL is already being generated. Please retry.",
        )

    db.refresh(db_quiz)
    return _quiz_to_response_dict(db_quiz)


@app.post("/generate-quiz-from-file", response_model=schemas.QuizResponse)
@limiter.limit(settings.generate_quiz_rate_limit)
async def generate_quiz_from_file(
    request: Request,  # required by slowapi's limiter decorator
    file: UploadFile = File(...),
    question_count: Optional[int] = Form(None),
    difficulty: str = Form("mixed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if difficulty not in schemas.DIFFICULTY_OPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"difficulty must be one of {schemas.DIFFICULTY_OPTIONS}",
        )
    if question_count is not None and not (
        schemas.MIN_QUESTION_COUNT <= question_count <= schemas.MAX_QUESTION_COUNT
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"question_count must be between {schemas.MIN_QUESTION_COUNT} and {schemas.MAX_QUESTION_COUNT}",
        )

    file_bytes = await file.read()

    try:
        document_text = extract_text_from_upload(
            filename=file.filename or "upload",
            content_type=file.content_type or "",
            file_bytes=file_bytes,
        )
    except DocumentExtractionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        quiz_data = quiz_generator.generate_quiz(
            document_text, question_count=question_count, difficulty=difficulty
        )
    except QuizGenerationError as e:
        logger.error("Quiz generation failed for uploaded file %s: %s", file.filename, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service failed to generate a quiz for this document. Please try again.",
        )

    # Uploads have no URL, so there's no natural dedup key -- every upload
    # creates a new quiz (unlike Wikipedia URLs, which dedupe per user).
    db_quiz = Quiz(
        owner_id=current_user.id,
        url=None,
        source_type="upload",
        question_count=len(quiz_data.quiz),
        difficulty=difficulty,
        title=file.filename or "Uploaded document",
        scraped_content=document_text,
    )
    db_quiz.set_quiz_data(quiz_data.model_dump())

    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    return _quiz_to_response_dict(db_quiz)


@app.post("/quizzes/{quiz_id}/attempt", response_model=schemas.QuizAttemptResponse)
def submit_quiz_attempt(
    quiz_id: int,
    attempt_data: schemas.QuizAttemptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Scoping by owner_id here (not just id) means requesting someone
    # else's quiz_id returns 404, not 403 -- it doesn't confirm the quiz
    # exists at all to a user who doesn't own it.
    quiz = (
        db.query(Quiz)
        .filter(Quiz.id == quiz_id, Quiz.owner_id == current_user.id)
        .first()
    )
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )

    quiz_data = quiz.get_quiz_data()
    quiz_questions = quiz_data.get("quiz", [])
    user_answers = attempt_data.answers

    if len(user_answers) != len(quiz_questions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected {len(quiz_questions)} answers, got {len(user_answers)}",
        )

    def is_answer_correct(user_answer, correct_answer, options):
        if not user_answer or not correct_answer:
            return False
        stripped_correct = correct_answer.strip().upper()
        if len(stripped_correct) == 1 and stripped_correct in ["A", "B", "C", "D"] and options:
            # The client stores the full option TEXT the user clicked
            # (see frontend QuizTaker's handleAnswerSelect), not a bare
            # letter -- so the correct letter has to be resolved to its
            # option text before comparing. Comparing user_answer's first
            # character to the letter directly (the previous behavior)
            # almost never matched, since option text rarely happens to
            # start with its own correct letter -- this was the root
            # cause of scores coming out near 0% regardless of what the
            # user actually selected.
            option_index = ord(stripped_correct) - ord("A")
            if 0 <= option_index < len(options):
                return user_answer.strip() == str(options[option_index]).strip()
        return user_answer.strip() == correct_answer.strip()

    correct_answers = sum(
        1
        for i, question in enumerate(quiz_questions)
        if is_answer_correct(user_answers[i], question["answer"], question.get("options", []))
    )

    total_questions = len(quiz_questions)
    score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        user_id=current_user.id,
        score=score_percentage,
        correct_answers=correct_answers,
        total_questions=total_questions,
        user_answers=user_answers,
        time_taken=attempt_data.time_taken,
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
        "answers": user_answers,
    }


@app.get("/quizzes/{quiz_id}/attempts", response_model=List[schemas.QuizAttemptResponse])
def get_quiz_attempts(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership first so this doesn't leak whether a quiz_id
    # belonging to another user exists.
    quiz = (
        db.query(Quiz)
        .filter(Quiz.id == quiz_id, Quiz.owner_id == current_user.id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz_id)
        .order_by(QuizAttempt.date_attempted.desc())
        .all()
    )

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

        result.append(
            {
                "id": attempt.id,
                "score": float(attempt.score),
                "correct_answers": attempt.correct_answers,
                "total_questions": attempt.total_questions,
                "time_taken": attempt.time_taken,
                "date_attempted": attempt.date_attempted,
                "answers": user_answers,
            }
        )

    return result


@app.get("/quizzes", response_model=schemas.PaginatedQuizHistory)
def get_quiz_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    total = (
        db.query(func.count(Quiz.id)).filter(Quiz.owner_id == current_user.id).scalar()
    )

    # Single aggregated query (LEFT JOIN + GROUP BY) instead of the
    # previous N+1 pattern (one extra query per quiz to fetch its
    # attempts). This was the one query in the whole app most likely to
    # fall over under real usage: fine with 10 quizzes, one query per quiz
    # by the time you have thousands.
    rows = (
        db.query(
            Quiz,
            func.count(QuizAttempt.id).label("attempts_count"),
            func.max(QuizAttempt.score).label("best_score"),
        )
        .outerjoin(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
        .filter(Quiz.owner_id == current_user.id)
        .group_by(Quiz.id)
        .order_by(Quiz.date_generated.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    items = [
        {
            "id": quiz.id,
            "url": quiz.url,
            "source_type": quiz.source_type,
            "question_count": quiz.question_count,
            "difficulty": quiz.difficulty,
            "title": quiz.title,
            "date_generated": quiz.date_generated,
            "attempts_count": attempts_count,
            "best_score": best_score,
        }
        for quiz, attempts_count, best_score in rows
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/quizzes/{quiz_id}", response_model=schemas.QuizResponse)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = (
        db.query(Quiz)
        .filter(Quiz.id == quiz_id, Quiz.owner_id == current_user.id)
        .first()
    )
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )
    return _quiz_to_response_dict(quiz)


@app.get("/health")
def health_check(db: Session = Depends(get_db), response: Response = None):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "message": "API and database are running",
            "database": "connected",
        }
    except Exception as e:
        logger.error("Health check failed: %s", e)
        if response is not None:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "message": "Database connection failed",
        }
