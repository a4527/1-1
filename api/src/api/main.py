from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, StringConstraints

from . import store

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title


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
