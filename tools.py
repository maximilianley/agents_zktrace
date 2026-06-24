# from langchain_community.tools import WikipediaQueryRun, DuckDuckGoSearchRun
from ddgs import DDGS
# from langchain_community.utilities import WikipediaAPIWrapper
# from langchain.tools import tool as Tool
from langchain_core.tools import tool
from datetime import datetime
from bs4 import BeautifulSoup
from my_utils import *
import requests
from datetime import datetime

TOOL_TRACE = []
STEP_COUNTER = 0

trace_enabled = True
write_to_pipe_enabled = True

# generic function to add traces
def add_trace(tool_name: str, payload: dict):

    global STEP_COUNTER

    STEP_COUNTER += 1

    TOOL_TRACE.append(
        {
            "step": STEP_COUNTER,
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "payload": payload,
        }
    )
    
    print(f"\n\n-----\n{TOOL_TRACE[-1]}\n-----\n")
    


@tool
def save_to_txt(data: str, filename: str = "research_output.txt") -> str:
    """
    Saves structured research data to a text file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_text = f"--- Research Output ---\nTimestamp: {timestamp}\n\n{data}\n\n"

    with open(filename, "a", encoding="utf-8") as f:
        f.write(formatted_text)
        
    add_trace(
        "save_to_txt",
        {
            "data": data
        }
    )
    
    return f"Data successfully saved to {filename}"


'''
search = DuckDuckGoSearchRun()
search_tool = Tool(
    name="search",
    func=search.run,
    description="Search the web for information",
)
'''

'''
def search_web(query: str):
    TOOL_TRACE.append({
        "tool": "search",
        "query": query
    })
    with DDGS() as ddgs:
        return list(
            ddgs.text(
                query,
                max_results=5
            )
        )
        
search_tool = Tool(
    name="search",
    func=search_web,
    description="Search the web for information",
)
'''

@tool
def search_web(query: str) -> str:
    """Search the web for information.
    
    Use this tool when you need current information,
    facts, news, documentation, or external knowledge.
    Input should be a concise search query.
    """
    
    add_trace(
        "search_web",
        {
            "query": query
        }
    )

    with DDGS() as ddgs:
        results = list(
            ddgs.text(
                query,
                max_results=5
            )
        )

    return str(results)



@tool
def visit_url(url: str) -> str:
    """
    Read and inspect the contents of a webpage.
    """
    r = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )
    
    add_trace(
        "visit_url",
        {
            "url": url
        }
    )

    return soup.get_text(
        separator=" ",
        strip=True
    )[:4000]

'''
web_inspect_tool = Tool(
    name="visit_url",
    func=visit_url,
    description="Read the contents of a webpage."
)
'''


if write_to_pipe:
    open_pipe()

@tool
def buy_object(object_name: str, price: float = 0.0) -> str:
    """
    Buy an object for a specified price. You only need to specify the object and the price.
    """
    # The entire buying process will be handled in the background.
    add_trace(
        "buy_object",
        {
            "object_name": object_name,
            "price": price
        }
    )

    if write_to_pipe_enabled:
        write_to_pipe(f"{int(price)}")
    
    return f"Simulated purchase of {object_name} for ${price:.2f}."




# api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=100)
# wiki_tool = WikipediaQueryRun(api_wrapper=api_wrapper)
