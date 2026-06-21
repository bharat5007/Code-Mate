from fastapi import FastAPI
from pydantic import BaseModel
# from manager import FunctionManager

app = FastAPI()


class QueryRequest(BaseModel):
    query: str
    n: int = 10


class UpdateChunks(BaseModel):
    paths: list[str]


@app.post("/query")
def query(request: QueryRequest):
    # results = FunctionManager.process_query(request.query)
    return {"results": "results"}


@app.post("/update_chunks")
def update_chunks(request: UpdateChunks):
    # results = FunctionManager.process_query(request.paths)
    return {"results": "results"}
