from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from dotenv import load_dotenv
import datetime
from .workers import SearchDataclass, search_agent, WriterDeps, writer_agent, RouterDeps, router, CollectData, collect_agent
from langgraph.types import StreamWriter

from sqlalchemy.orm import Session
# Import the message classes from Pydantic AI

import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
load_dotenv()
       
class SystemState(TypedDict):
    research_results: str
    query: str
    iteration: int

async def data_collector(state: SystemState, writer:StreamWriter):
    writer({"update": "Finding out what data we need...", "done": False})
    deps = CollectData(writer = writer)
    print(state['query'])
    await collect_agent.run(state['query'], deps = deps)
    return

    
async def research(state: SystemState,  writer: StreamWriter):  
    writer({"update": "Thinking...", "done": False})

    # Use the same dependency type as defined in the agent.
    deps = SearchDataclass(writer=writer, max_results=5)
    result =  await search_agent.run(state['query'], deps=deps) 
    result = result.output.strip()
    
    return {"research_results": result}


async def write(state: SystemState, writer: StreamWriter):

    deps = WriterDeps(query=state["query"] )

    if state["research_results"] == "none":
        prompt = f"USER_QUERY: {state["query"]}"
    else:
        prompt= f"USER_QUERY: {state["query"]}\n\nRESEARCH: {state["research_results"]}"

    print(f"PROMPT:{prompt}")
    text = ""
    async with writer_agent.run_stream(prompt, deps=deps) as s:
        async for tok in s.stream_text(debounce_by=None):
            text += tok
            writer({"response": tok, "done": False})
        
    return {"current_text": text}


async def route_router(state:SystemState, writer:StreamWriter):
    if state["iteration"] >= 0: ## cycles 1 time at most 
        writer({"done":True})
        return "END"

    state["iteration"] += 1
    
    prompt = f"""
    Is the following text satisfactory to all the requirements of the assignment and the users remarks?

    TEXT:
    {state["query"]}

    """

    deps = RouterDeps(query = state["query"])

    result = await router.run(prompt, deps = deps) 

    result = result.data.boolean

    if result == "true":
        writer({"done":True})
        return "END"
    
    
    return "define_scope_with_reasoner"
    
builder = StateGraph(SystemState)
builder.add_node("data_collector", data_collector)
builder.add_node("research", research)
builder.add_node("write", write)
builder.add_node("router", route_router)

builder.add_edge(START, "data_collector")
builder.add_edge("data_collector", "research")
builder.add_edge("research", "write")


builder.add_conditional_edges(
    "write", 
    route_router,
    {"research": "research", "END": END}
)

agent_flow = builder.compile()

async def run_agent(user_input:str):
    
    config = {
        "configurable":{
            "thread_id": 1
        }
    }

    async for msg in agent_flow.astream(
        {"query": user_input, "iteration": 0}, 
        config, 
        stream_mode = "custom"   
    ):  
        yield msg

        if type(msg) == dict and msg["done"]:
            return 
        
