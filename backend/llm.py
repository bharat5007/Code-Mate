from typing import TypedDict, Annotated, Literal
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver


load_dotenv()

######################### Constants #########################
MAX_TOKENS = 150


######################### Schemas #########################
class ConditionalSchema(BaseModel):
    output: Literal["question/answer", "tools"] = Field(
        description="Type of pipeline to choose"
    )


######################### Models #########################
model = ChatGroq(model="llama-3.3-70b-versatile", temperature=1)
conditional_model = model.with_structured_output(ConditionalSchema)


######################### GRAPH STATE #########################
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


######################### Functions #########################
def decide_pipeline(state: ChatState):
    prompt = f"Given query {state['messages'][-1]} you have to decide what kind of pipeline will be best for this."
    result = conditional_model.invoke(prompt)
    if result.output == "tools":
        return "call_tools"

    return "question_answer"


def fetch_data(state: ChatState):
    # fetch data based on query
    pass


def call_tools(state: ChatState):
    # call desired tools based on query
    pass


def question_answer(state: ChatState):
    messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=MAX_TOKENS,
    )

    response = model.invoke(messages)
    return {"messages": [response]}


######################### Graph Initialization #########################
checkpointer = InMemorySaver()
graph = StateGraph(ChatState)

graph.add_node("decide_pipeline", decide_pipeline)
graph.add_node("fetch_data", fetch_data)
graph.add_node("question_answer", question_answer)
graph.add_node("call_tools", call_tools)

graph.add_edge(START, "fetch_data")
graph.add_conditional_edges("fetch_data", "decide_pipeline")
graph.add_edge("question_answer", END)
graph.add_edge("call_tools", END)
