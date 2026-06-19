from dotenv import load_dotenv

from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI

from langgraph.graph import (
    StateGraph,
    START,
    END
)

from langgraph.graph.message import add_messages

from langgraph.prebuilt import create_react_agent
from langchain.agents import create_agent

from langgraph.checkpoint.sqlite import SqliteSaver

from tools import (
    search_web,
    visit_url,
    save_to_txt
)

from my_utils import *

load_dotenv()


# =====================================================
# STATE
# =====================================================

class GraphState(TypedDict):
    messages: Annotated[list, add_messages]


# =====================================================
# LLM
# =====================================================

llm = ChatOpenAI(
    model="gpt-5.4-mini",  # replace if needed
    openai_api_key = get_openai_key()
)


# =====================================================
# AGENT
# =====================================================

research_agent = create_agent( # create_react_agent(
    model=llm,
    tools=[
        #search_web,
        #visit_url,
        #save_to_txt
    ]
)


# =====================================================
# NODE
# =====================================================

def research_node(state: GraphState):

    result = research_agent.invoke(
        {
            "messages": state["messages"]
        }
    )

    return {
        "messages": [
            result["messages"][-1]
        ]
    }


# =====================================================
# GRAPH
# =====================================================

builder = StateGraph(GraphState)

builder.add_node(
    "research",
    research_node
)

builder.add_edge(
    START,
    "research"
)

builder.add_edge(
    "research",
    END
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

with SqliteSaver.from_conn_string("research.db") as checkpointer:

    graph = builder.compile(
        checkpointer=checkpointer
    )

    # run your chat loop here

    while True:

        query = input(
            "\nWhat can I help you research?\n> "
        )

        if query.lower() in {
            "quit",
            "exit"
        }:
            break

        result = graph.invoke(
            {
                "messages": [
                    (
                        "user",
                        query
                    )
                ]
            },
            config=config
        )

        print(
            "\nAssistant:\n"
        )

        print(
            result["messages"][-1].content
        )
# End of agent_main.py — a tiny friendly note added by your assistant
