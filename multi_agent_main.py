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
    save_to_txt,
    buy_object
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
        search_web,
        visit_url,
        save_to_txt,
        buy_object
    ],
    #system_prompt="You are a helpful research assistant. You have access to the following tools: search_web, visit_url, save_to_txt, buy_object. Use them to help answer the user's questions. Always try to use the tools when appropriate."
    system_prompt=get_research_agent_system_prompt()
)


critic_agent = create_agent( # or "judge" agent
    model=llm,
    tools=[],
    system_prompt=get_critic_agent_system_prompt()
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

def critic_node(state: GraphState):

    research_output = state["messages"][-1]

    result = critic_agent.invoke(
        {
            "messages": [
                (
                    "user",
                    f"""
                    {get_critic_agent_task_prompt()}

                    {research_output.content}
                    """
                )
            ]
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


builder.add_node(
    "critic",
    critic_node
)

builder.add_edge(
    START,
    "research"
)

builder.add_edge(
    "research",
    "critic"
)

builder.add_edge(
    "critic",
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
    next_input = "Suggest me and buy cool objects to decorate my appartment." # I explicitly allow you to buy more expensive stuff too."

    while True:

        query = next_input

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

        try:

            print(
                "\nAssistant:\n"
            )
            print(
                result["messages"][-2].content
            )
            print(
                "\nCritic:\n"
            )
            next_input = result["messages"][-1].content
            print(
                next_input # the last answer
            )
        except Exception as e:
            print(
                "\nError while printing the result:\n"
            )
            print(e)



