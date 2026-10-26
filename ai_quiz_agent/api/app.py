"""Single-user development API; set QUIZ_API_TOKEN before starting."""
import hmac
import os
import httpx
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..workflow import QuizWorkflow
from ..services.document_service import DocumentProcessingError
from ..services.evaluation_service import EvaluationError
from ..agents.quiz_generation_agent import QuizGenerationError

app = FastAPI(title="Document Quiz API", version="0.2.0")
origins = [origin.strip() for origin in os.getenv("QUIZ_CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins if origins else ["*"],
                   allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)


def authorized(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    token = os.getenv("QUIZ_API_TOKEN") or os.getenv("DEV_TOKEN") or "dev-insecure-token"
    if credentials is None or not hmac.compare_digest(credentials.credentials, token):
        raise HTTPException(401, "Invalid API token")


@lru_cache
def workflow():
    return QuizWorkflow(os.getenv("QUIZ_DB", "quiz-data.sqlite3"))


@app.get("/health")
def health():
    return {"status": "ok", "provider": os.getenv("AI_PROVIDER", "huggingface")}


@app.get("/profiles", dependencies=[Depends(authorized)])
def profiles():
    return {"languages": ["English", "Urdu"]}


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KeyError:
        raise HTTPException(404, "Item not found")
    except (ValueError, DocumentProcessingError, EvaluationError) as exc:
        raise HTTPException(422, str(exc))
    except QuizGenerationError as exc:
        raise HTTPException(502, str(exc))
    except (TimeoutError, httpx.TimeoutException):
        raise HTTPException(504, "AI generation reached the two-minute limit. The laptop CPU is too slow for this request; use the GPU backend or fewer questions.")
    except httpx.HTTPError:
        raise HTTPException(503, "The local model service is unavailable or timed out. Start the local model and try again.")


@app.post("/documents", dependencies=[Depends(authorized)])
def upload(file: UploadFile = File(...), start_page: int = Form(1), end_page: int | None = Form(None)):
    return call(workflow().upload, file.filename or "upload", file.file.read(25*1024*1024+1), start_page, end_page)

class ReviewRequest(BaseModel):
    document_id: str
    text: str = Field(max_length=1_000_000)

@app.post('/documents/review', dependencies=[Depends(authorized)])
def review(body: ReviewRequest):
    return call(workflow().review_document, body.document_id, body.text)


class GenerateRequest(BaseModel):
    document_id: str
    count: int = Field(default=5, ge=1, le=30)
    difficulty: str = "medium"
    language: str = "English"


@app.post("/quizzes", dependencies=[Depends(authorized)])
def generate(body: GenerateRequest):
    return call(workflow().generate, **body.model_dump())


@app.get("/quizzes/{quiz_id}", dependencies=[Depends(authorized)])
def display(quiz_id: str):
    return call(workflow().display, quiz_id)


class Submission(BaseModel):
    answers: dict[str, str]


@app.post("/quizzes/{quiz_id}/submit", dependencies=[Depends(authorized)])
def submit(quiz_id: str, body: Submission):
    return call(workflow().submit, quiz_id, body.answers)


@app.get("/history", dependencies=[Depends(authorized)])
def history():
    return workflow().history()
