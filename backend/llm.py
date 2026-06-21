from typing import TypedDict, Annotated, Any, List, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from constants import sessions

load_dotenv()

######################### Constants #########################
MAX_TOKENS = 150
config = {"configurable": {"thread_id": "thread"}}


######################### Schemas #########################
class SimilarQueries(BaseModel):
    queries: List[str] = Field(description="3 similar queries")


class AnswerQuery(BaseModel):
    response: str = Field(description="Response for given query")
    confidence: int = Field(description="Higher confidence means need to use tool")
    summary: str = Field(description="New summary of chat")
    required_tool: Literal["edit_code", "read_code", "run_terminal", "none"] = Field(
        description="Which tools is required to run"
    )


######################### Models #########################
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=1)
query_model = model.with_structured_output(SimilarQueries)
answer_query = model.with_structured_output(AnswerQuery)


######################### GRAPH STATE #########################
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    summary: str = None
    repo_path: str
    chunks: list[Any] = None
    confidence: int
    tool_calls_count: int


######################### Functions #########################
def fetch_chunks(state: ChatState):
    retriver = sessions.get(state["repo_path"]["retriver"])
    chunks = retriver.retrive(state["messages"][-1])
    return {"chunks": chunks}


def generate_similar_queries(state: ChatState):
    prompt = f"""
    Ask 3 similar question based on given query {state["messages"][-1]}
    given chunks are {state["chunks"]}
    """
    response = query_model.invoke(prompt)
    chunks = []

    retriver = sessions.get(state["repo_path"]["retriver"])
    for query in response:
        chunks.extend(retriver.retrive(query))

    return {"chunks": chunks}


def call_llm(state: ChatState):
    # messages
    last_messages = (
        state["messages"][0:5] if len(state["messages"]) >= 5 else state["messages"]
    )
    chunks = state["chunks"]
    summary = state["summary"]
    query = state["messages"][-1]

    prompt = f"""
    given last messages: {last_messages}, chat_summary: {summary},
    chunks: {chunks}. Answer the query: {query} based on given data.
    Generate a confidence score if a tool is needed to be used. Also 
    generate a new summary of chat
    """

    result = answer_query.invoke(prompt)
    return {
        "messages": result.response,
        "confidence": result.confidence,
        "summary": result.summary,
    }


def check_tools_required(state: ChatState):
    if (
        state["tool_calls_count"] >= 5
        or state["confidence"] < 0.7
        or state["required_tool"] == "none"
    ):
        return "reset_state"

    return "call_tools"


def call_tools(state: ChatState):
    # call desired tools based on query
    pass


def reset_state(state: ChatState):
    return {"tool_calls_count": 0}


######################### Graph Initialization #########################
checkpointer = InMemorySaver()
graph = StateGraph(ChatState)

# Add Nodes
graph.add_node("fetch_chunks", fetch_chunks)
graph.add_node("generate_similar_queries", generate_similar_queries)
graph.add_node("call_llm", call_llm)
graph.add_node("call_tools", call_tools)
graph.add_node("reset_state", reset_state)

# Add Edges
graph.add_edge(START, "fetch_chunks")
graph.add_edge("fetch_chunks", "generate_similar_queries")
graph.add_edge("generate_similar_queries", "call_llm")
graph.add_conditional_edges("call_llm", check_tools_required)
graph.add_edge("call_tools", "call_llm")
graph.add_edge("reset_state", END)

chatbot = graph.compile(checkpointer=checkpointer)


######################### Utils #########################
def fetch_thread_ids():
    threads = set()
    for checkpoint in checkpointer.list(None):
        threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(threads)
