from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from . import store

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Annotated[str, StringConstraints(max_length=1000)] | None = None
    due_date: date | None = None
    priority: Literal["urgent", "normal", "low"] | None = None
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
    store.init_db()
    yield


app = FastAPI(title="task-flow", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tasks")
def list_tasks() -> list[dict]:
    return store.list_tasks()


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskCreate) -> dict:
    return store.create_task(body.title)


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskPatch) -> dict:
    fields = body.model_dump(mode="json", include=body.model_fields_set)
    task = store.update_task(task_id, fields)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int) -> Response:
    if not store.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=204)
