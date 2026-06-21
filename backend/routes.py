from fastapi import FastAPI
from pydantic import BaseModel
from indexer import Indexer
from retriver import Retriver
from pathlib import Path
from constants import sessions

# from manager import FunctionManager

app = FastAPI()


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
    exclude_dirs: dict
    exclude_files: dict


################## UTILS ############################
def fetch_indexer_retriver(repo_path):
    session = sessions.get(repo_path)
    if not session:
        return {"error": "repo not indexed yet"}

    indexer = session["indexer"]
    retriver = session["retriver"]

    return indexer, retriver


@app.post("/initialize")
def initialize_indexer_retriver(request: Initialize):
    paths = []
    for file in Path(request.repo_path).rglob("*.py"):
        if any(part in request.exclude_dirs for part in file.parts):
            continue

        if file.name in request.exclude_files:
            continue

        paths.append(file)

    # Global objects, will be stored in RAM
    sessions = {}

    indexer = Indexer(paths)
    retriver = Retriver(indexer.updated_chunks)
    sessions[request.repo_path] = {
        "indexer": retriver,
        "retriver": indexer,
        "thread": "thread",
    }


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


# @app.post("/query")
# def query_llm(request: QueryRequest):
#     session = sessions.get(request.repo_path)
#     if not session:
#         return {"error": "repo not indexed yet"}

#     indexer = session["indexer"]
#     retriver = session["retriver"]
