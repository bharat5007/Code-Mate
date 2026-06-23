from fastapi import FastAPI, Query
from pydantic import BaseModel
from indexer import Indexer
from retriver import Retriver
from pathlib import Path
from constants import sessions
from llm import chatbot
import truststore
from typing import Optional
from langgraph.types import Command

truststore.inject_into_ssl()


app = FastAPI()
CONFIG = {"configurable": {"thread_id": "thread"}}


class QueryRequest(BaseModel):
    repo_path: str
    thread_id: Optional[str] = None
    query: str
    n: int = 10


class UpdateChunks(BaseModel):
    repo_path: str
    paths: list[str]


class FetchChunks(BaseModel):
    repo_path: str
    query: str


class Initialize(BaseModel):
    repo_path: str
    exclude_dirs: list[str] = []
    exclude_files: list[str] = []


class ApproveEdit(BaseModel):
    thread_id: str
    decision: str


################## UTILS ############################
def fetch_indexer_retriver(repo_path):
    session = sessions.get(repo_path)
    if not session:
        return {"error": "repo not indexed yet"}

    indexer = session["indexer"]
    retriver = session["retriver"]

    return indexer, retriver


@app.post("/initialize")
async def initialize_indexer_retriver(request: Initialize):
    print(f"<<<<<<<<<< {request.repo_path}")
    if sessions.get(request.repo_path):
        return {"Message": "Indexing completed", "Indexing_exist": True}

    paths = []
    for file in Path(request.repo_path).rglob("*.py"):
        if any(part in request.exclude_dirs for part in file.parts):
            continue

        if file.name in request.exclude_files:
            continue

        paths.append(file)

    indexer = Indexer(paths)
    retriver = Retriver(indexer.updated_chunks)
    sessions[request.repo_path] = {
        "indexer": indexer,
        "retriver": retriver,
    }

    return {"Message": "Indexing completed", "Indexing_exist": False}


@app.get("/messages")
def fetch_messages(repo_path: str = Query(...), thread_id: str = Query(...)):
    messages = sessions.get(thread_id, [])
    return {"messages": messages}


@app.post("/update_chunks")
def update_indexer_retriver(request: UpdateChunks):
    session = sessions.get(request.repo_path)
    if not session:
        return {"error": "repo not indexed yet"}

    indexer = session["indexer"]
    retriver = session["retriver"]

    indexer.update_tree(request.paths)
    if indexer.updated_chunks:
        retriver.bm25_remove_chunks(request.paths)
        retriver.bm25_add_chunks(indexer.updated_chunks)
        retriver.faiss_add_chunks(indexer.updated_chunks, indexer.removed_chunks)
    return {"status": "updated"}


@app.get("/chunks")
def fetch_chunks(request: FetchChunks):
    _, retriver = fetch_indexer_retriver(request.repo_path)
    response = retriver.retrive(request.query)
    return response


@app.post("/query")
def query_llm(request: QueryRequest):
    messages = sessions.get(request.thread_id, [])
    messages.append(request.query)
    config = (
        {"configurable": {"thread_id": request.thread_id}}
        if request.thread_id
        else CONFIG
    )
    response = chatbot.invoke(
        {"messages": [request.query], "repo_path": request.repo_path}, config=config
    )

    if response.get("__interrupt__"):
        interrupt_data = response["__interrupt__"][0].value
        return {"pending_edit": interrupt_data}

    ai_message = response.get("messages", [])[-1]
    if ai_message:
        ai_message = ai_message.content
    else:
        "No response from bot"

    messages.append(ai_message)
    sessions[request.thread_id] = messages
    print(f"!!!!!!!!!!!     {response}")
    return {"results": ai_message}


@app.post("/approve_edit")
def approve_edit(request: ApproveEdit):
    response = chatbot.invoke(
        Command(resume=request.decision),
        config={"configurable": {"thread_id": request.thread_id}},
    )

    ai_message = response.get("messages", [])[-1]
    return {"results": ai_message.content if ai_message else "Edit applied."}
