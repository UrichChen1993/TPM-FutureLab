from langchain.agents import create_agent

from agent.llm import build_llm
from agent.prompts import SYSTEM_PROMPT
from agent.tools import build_tools


def build_agent_executor(repo, clock, user_id: str):
    llm = build_llm()
    tools = build_tools(repo, clock, user_id)
    return create_agent(model=llm, tools=tools, system_prompt=SYSTEM_PROMPT)
