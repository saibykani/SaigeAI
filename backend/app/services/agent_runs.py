"""Agent execution records (spec section 40): every agent run is persisted with its inputs,
outputs, actions, errors and timing."""

from contextlib import asynccontextmanager
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import collections as c
from app.services.audit import redact
from app.utils import new_id, utcnow


class AgentRun:
    def __init__(self, agent_name: str, user_id: str, input_: dict[str, Any]) -> None:
        self.id = new_id()
        self.agent_name = agent_name
        self.user_id = user_id
        self.input = input_
        self.output: dict[str, Any] = {}
        self.actions: list[str] = []
        self.errors: list[str] = []

    def action(self, text: str) -> None:
        if len(self.actions) < 500:
            self.actions.append(text)


@asynccontextmanager
async def agent_run(db: AsyncIOMotorDatabase, agent_name: str, user_id: str, input_: dict[str, Any]):
    run = AgentRun(agent_name, user_id, input_)
    start = utcnow()
    await db[c.AGENT_RUNS].insert_one({
        "_id": run.id, "agent_name": agent_name, "user_id": user_id, "status": "running",
        "start_time": start, "input": redact(input_),
    })
    status = "succeeded"
    try:
        yield run
    except Exception as exc:
        status = "failed"
        run.errors.append(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if status == "succeeded" and run.errors:
            status = "partial"
        await db[c.AGENT_RUNS].update_one({"_id": run.id}, {"$set": {
            "status": status, "end_time": utcnow(),
            "duration_ms": round((utcnow() - start).total_seconds() * 1000),
            "output": redact(run.output), "actions": run.actions, "errors": run.errors,
        }})
