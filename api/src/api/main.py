from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from . import auth, briefing, store, suggest
from .suggest import Priority

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=254)]
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        if not auth.EMAIL_RE.match(v):
            raise ValueError("이메일 형식이 아닙니다.")
        return v


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title


class SuggestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Annotated[str, StringConstraints(max_length=1000)] = ""


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: Title
    description: Annotated[str, StringConstraints(max_length=1000)] = ""


class BriefingTop(BaseModel):
    id: int
    reason: str


class BriefingResponse(BaseModel):
    top3: list[BriefingTop]
    later: list[int]
    cheer: str


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Annotated[str, StringConstraints(max_length=1000)] | None = None
    due_date: date | None = None
    priority: Priority | None = None
    status: Literal["todo", "in_progress", "done"] | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "TaskPatch":
        sent = self.model_fields_set
        if not sent:
            raise ValueError("바꿀 필드를 하나 이상 보내야 합니다.")
        if "status" in sent and len(sent) > 1:
            raise ValueError("status는 다른 필드와 함께 보낼 수 없습니다.")
        for name in ("title", "priority", "status"):
            if name in sent and getattr(self, name) is None:
                raise ValueError(f"{name}은 null일 수 없습니다.")
        return self


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.check_schema()
    yield


app = FastAPI(title="task-flow", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/signup", status_code=201)
def signup(body: Credentials, response: Response) -> dict:
    password_hash = auth.hash_password(body.password)
    existing = store.get_user_by_email(body.email)
    if existing and existing["password_hash"] is None:
        # M2 이전 Task의 주인 계정: 비밀번호를 처음 정한 사람이 넘겨받는다 (D-010)
        if not store.claim_user(existing["id"], password_hash):
            raise HTTPException(status_code=409, detail="Email already registered")
        user = {"id": existing["id"], "email": existing["email"]}
    else:
        user = store.create_user(body.email, password_hash)
        if user is None:
            raise HTTPException(status_code=409, detail="Email already registered")
    auth.start_session(response, user["id"])
    return user


@app.post("/api/auth/login")
def login(body: Credentials, response: Response) -> dict:
    user = store.get_user_by_email(body.email)
    if user is None or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    auth.start_session(response, user["id"])
    return {"id": user["id"], "email": user["email"]}


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response, taskflow_session: str | None = Cookie(default=None)) -> Response:
    auth.end_session(response, taskflow_session)
    response.status_code = 204
    return response


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.current_user)) -> dict:
    return user


@app.get("/api/tasks")
def list_tasks(user: dict = Depends(auth.current_user)) -> list[dict]:
    return store.list_tasks(user["id"])


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskCreate, user: dict = Depends(auth.current_user)) -> dict:
    return store.create_task(user["id"], body.title)


@app.post("/api/tasks/suggest")
def suggest_task(body: SuggestRequest, user: dict = Depends(auth.current_user)) -> dict:
    return suggest.suggest(body.title, body.description)


@app.post("/api/tasks/generate")
def generate_tasks(body: GenerateRequest, user: dict = Depends(auth.current_user)) -> dict:
    return suggest.generate(body.topic, body.description)


@app.post("/api/tasks/briefing", response_model=BriefingResponse)
def task_briefing(user: dict = Depends(auth.current_user)) -> dict:
    return briefing.briefing(user["id"])


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskPatch, user: dict = Depends(auth.current_user)) -> dict:
    fields = body.model_dump(mode="json", include=body.model_fields_set)
    task = store.update_task(user["id"], task_id, fields)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, user: dict = Depends(auth.current_user)) -> Response:
    if not store.delete_task(user["id"], task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=204)
