from dotenv import load_dotenv

from typing import TypedDict

from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from typing import Annotated
from langgraph.graph.message import add_messages

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from langgraph.checkpoint.sqlite import SqliteSaver

from tools import *

load_dotenv()


# =====================================================
# OUTPUT MODEL
# =====================================================

class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]


# =====================================================
# GRAPH STATE
# =====================================================

class GraphState(TypedDict):
    query: str
    research_text: str
    response: ResearchResponse


# =====================================================
# LLM
# =====================================================

llm = ChatOpenAI(
    model="gpt-5.4-mini"
)


# =====================================================
# RESEARCH AGENT
# =====================================================

research_agent = create_react_agent(
    model=llm,
    tools=[
        search_web,
        visit_url,
        save_text_to_file,
    ]
)


def research_node(state: GraphState):

    result = research_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=state["query"]
                )
            ]
        }
    )

    final_message = result["messages"][-1]

    return {
        "research_text": final_message.content
    }


# =====================================================
# FORMATTER
# =====================================================

structured_llm = llm.with_structured_output(
    ResearchResponse
)

formatter_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a research formatter.

            Convert the provided research result into
            a valid ResearchResponse.

            Infer:
            - topic
            - summary
            - sources
            - tools_used

            If sources are not explicitly available,
            return an empty list.
            """
        ),
        (
            "human",
            "{research}"
        )
    ]
)


def formatter_node(state: GraphState):

    chain = formatter_prompt | structured_llm

    response = chain.invoke(
        {
            "research": state["research_text"]
        }
    )

    return {
        "response": response
    }


# =====================================================
# BUILD GRAPH
# =====================================================

builder = StateGraph(GraphState)

builder.add_node(
    "research",
    research_node
)

builder.add_node(
    "formatter",
    formatter_node
)

builder.add_edge(
    START,
    "research"
)

builder.add_edge(
    "research",
    "formatter"
)

builder.add_edge(
    "formatter",
    END
)


# =====================================================
# MEMORY
# =====================================================

checkpointer = SqliteSaver.from_conn_string(
    "research.db"
)

graph = builder.compile(
    checkpointer=checkpointer
)


# =====================================================
# THREAD
# =====================================================

config = {
    "configurable": {
        "thread_id": "research-session-1"
    }
}


# =====================================================
# CHAT LOOP
# =====================================================

while True:

    query = input(
        "\nWhat can I help you research?\n> "
    )

    if query.lower() in {
        "exit",
        "quit"
    }:
        break

    result = graph.invoke(
        {
            "query": query
        },
        config=config
    )

    response: ResearchResponse = result["response"]

    print("\n" + "=" * 60)

    print("\nTOPIC")
    print(response.topic)

    print("\nSUMMARY")
    print(response.summary)

    print("\nSOURCES")
    for source in response.sources:
        print("-", source)

    print("\nTOOLS USED")
    for tool in response.tools_used:
        print("-", tool)

    print("\n" + "=" * 60)
