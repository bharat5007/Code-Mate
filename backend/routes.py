from fastapi import FastAPI
from pydantic import BaseModel
from indexer import Indexer
from retriver import Retriver
from pathlib import Path
from constants import sessions
from llm import chatbot
import truststore

truststore.inject_into_ssl()

# from manager import FunctionManager

app = FastAPI()
CONFIG = {"configurable": {"thread_id": "thread"}}


class QueryRequest(BaseModel):
    repo_path: str
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
        "thread": "thread",
    }

    return {"Message": "Indexing completed"}


@app.put("/chunks")
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
    response = chatbot.invoke(
        {"messages": [request.query], "repo_path": request.repo_path}, config=CONFIG
    )
    ai_message = response.get("messages", [])[-1]
    if ai_message:
        ai_message = ai_message.content
    else:
        "No response from bot"

    print(f"!!!!!!!!!!!     {response}")
    return {"results": ai_message}
