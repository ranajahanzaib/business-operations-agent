"""Durable LangGraph boundary for the local workflow lifecycle."""

from __future__ import annotations

import os
from typing import TypedDict

os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .api import execute_agent
from .db import DB_PATH, connect


class WorkflowState(TypedDict, total=False):
    run_id: str
    request: str
    gate: dict
    status: str


async def prepare(state: WorkflowState) -> dict:
    await execute_agent(state["run_id"], state["request"])
    with connect() as c:
        status = c.execute("SELECT status FROM runs WHERE id=?", (state["run_id"],)).fetchone()[0]
    return {"status": status}


def approval_gate(state: WorkflowState) -> dict:
    result = interrupt({"run_id": state["run_id"], "approval_required": True})
    return {"gate": result}


def finish(state: WorkflowState) -> dict:
    return {}


def route(state: WorkflowState) -> str:
    return "approval_gate" if state.get("status") == "awaiting_approval" else "finish"


def graph_builder():
    builder = StateGraph(WorkflowState)
    builder.add_node("prepare", prepare)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("finish", finish)
    builder.add_edge(START, "prepare")
    builder.add_conditional_edges(
        "prepare", route, {"approval_gate": "approval_gate", "finish": "finish"}
    )
    builder.add_edge("approval_gate", "finish")
    builder.add_edge("finish", END)
    return builder


async def start(run_id: str, request: str) -> None:
    path = str(DB_PATH.with_name("opsagent-checkpoints.sqlite3"))
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        graph = graph_builder().compile(checkpointer=saver)
        await graph.ainvoke(
            {"run_id": run_id, "request": request}, {"configurable": {"thread_id": run_id}}
        )


async def resume(run_id: str, approved: bool) -> None:
    path = str(DB_PATH.with_name("opsagent-checkpoints.sqlite3"))
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        graph = graph_builder().compile(checkpointer=saver)
        await graph.ainvoke(
            Command(resume={"approved": approved}), {"configurable": {"thread_id": run_id}}
        )
