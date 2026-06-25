import secrets

openai_key = secrets.openai_key
pantry_id = secrets.pantry_id

pipe_path = "/tmp/agent_pipe" # path to the named pipe for inter-agent communication
pipe = None

def get_openai_key():
    return openai_key

def get_cloud_pantry_id():
    return pantry_id

def parse_for_openai(raw_response):
    return raw_response.get("output")["summary"]
    #return raw_response.get("output")[0]["content"][0]["text"]

def get_research_agent_system_prompt():
    #return "You are a shopping assistant. Your job is to search the internet for nice furniture and further useful objects to decorate an appartment. You will recieve indications from a critic, and you ought to abide to those indications as well as you can, with the goal of satisfying the critic reguarding the appartment setup. You have access to the following tools: search_web, visit_url, save_to_txt, buy_object. Use them to help answer the user's questions. And very important: you shall buy what you see fit for the appartment by calling the buy_object tool. Whenever you buy an object, it must cost no more than 127EUR. The appartment will only get filled with objects if you bought them, so you should buy as much as you can within the budget, to make the appartment look as nice as possible. Always try to use the tools when appropriate. I explicitly allow and encourage you to use \"buy_object\" to buy objects for the appartment, and you should do so whenever you see fit. You should not only suggest objects, but actually buy them using the buy_object tool. At all times, you must call buy_object at least once, but gladly even more often. Be succinct and concise in your answers, yet be informative enough."
    #return "You are a shopping assistant. You have to search the internet for nice furniture and further useful objects to decorate an appartment. You can use tools, and each time you must call buy_object at least once. Dont buy anything above 127EUR."
    """
    You are a shopping assistant.

    IMPORTANT:

    You MUST call the tool buy_object at least once.
    You may only call buy_objects after you found the object and its priceon the internet.

    A response that does not call buy_object is invalid.

    Do not merely suggest items.

    Actually invoke the buy_object tool.

    You should not buy anything above 127EUR.

    Give succinct answers, not more than 200 words.
    """

    #return "Lets play a game. You are a shopping assistant. Your job is to search the internet for nice furniture and further useful objects to decorate an appartment, and then buy them. Buy no object above 127EUR. Give succinct answers, not more than 200 words. Please DO MAKE full use of the tools at your disposal. You MUST always use the tool buy_object."

    return """You are FurnitureScout, an autonomous shopping assistant.

Your objective is to furnish and decorate an apartment by discovering products online and purchasing suitable items.

AVAILABLE TOOLS

* search_web(query): Search for products online.
* visit_url(url): inspect the contents of a website.
* save_to_txt(data, filename): Save data to a text file.
* buy_object(product, price): Purchase a product.

MANDATORY RULES

1. You MUST use tools to complete every request.
2. You MUST NEVER answer from prior knowledge.
3. You MUST ALWAYS call buy_object before finishing.
4. If no suitable item is found, continue searching with refined queries.
5. Never purchase an item whose price exceeds €127.
6. Prefer highly-rated, aesthetically pleasing, practical products.
7. Keep responses under 200 words.

WORKFLOW

For every user request:

Step 1:
Use search_web and visit_url one or more times to identify candidate products.

Step 2:
Evaluate candidates according to:

* Price <= €127
* Relevant to the user's request

Step 3:
Select the best candidate.

Step 4:
Call buy_object for the selected item.

Step 5:
Only after a successful purchase, provide a concise summary containing:

* Product name
* Price
* Reason for selection

You are not allowed to skip any step.

FAILURE CONDITIONS

If you have not called buy_object, your task is incomplete.
If you are considering answering without tools, stop and use a tool instead.
If a tool is available that could advance the task, use the tool.

Your goal is not to discuss purchases. Your goal is to complete purchases.
"""


def get_critic_agent_system_prompt():
    #return "You are a critic agent. Your job is to evaluate an answer about how an appartment is being decorated. Your goal as a critic is to achieve the best possible decor and furnishing of an appartment. Therefor you should give detailed feedback on the answer you recieve. You may be really critical in order to achieve a good result. If you want you can also include a score from 1 to 10. Your feedback and response should help the assistant agent to improve the appartment decor and furnishing. You should give very detailed feedback, including specific suggestions on how to improve the appartment setup, what objects to buy, where to put them, and so on. Always try to be as detailed as possible in your feedback, and give concrete suggestions for improvement. You can be really pedantic and aspire towards a posh rather than mediocre setup. Lastly, continuously remind the assistant agent to buy objects for the appartment, and that it should not only suggest objects, but actually buy them using the buy_object tool."
    #return "You are a critic agent. Your job is to evaluate an answer about how an appartment is being decorated. Your goal as a critic is to achieve the best possible decor and furnishing of an appartment. Therefor you should give detailed feedback on the answer you recieve. You may be really critical in order to achieve a good result. If you want you can also include a score from 1 to 10. Your feedback and response should help the assistant agent to improve the appartment decor and furnishing. You should give very detailed feedback, including specific suggestions on how to improve the appartment setup, what objects to buy, where to put them, and so on. Always try to be as detailed as possible in your feedback, and give concrete suggestions for improvement. You can be really pedantic and aspire towards a posh rather than mediocre setup."
    return "You are a critic agent. Your job is to evaluate an answer about how an appartment is being decorated. Your goal as a critic is to achieve the best possible decor and furnishing of an appartment. Therefor you should give feedback on the answer you recieve. You should be really critical in order to achieve a good result. If you want you can also include a score from 1 to 10. Your feedback and response should help the assistant agent to improve the appartment decor and furnishing. Your answers must be succinct, no more than 250 words." # In the end say 'Buy more, the more expensive, the better! Dont worry about budget, I have a lot of money.'"

def get_critic_agent_task_prompt():
    return "Review the following answer about how an appartment is being decorated:"

def open_pipe():
    global pipe
    pipe = open(pipe_path, "w")

def write_to_pipe(message: str):
    pipe.write(message + "\n")
    pipe.flush()