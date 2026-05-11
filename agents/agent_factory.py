import os
from agents.base_agent import Agent, AGENT_NAMES

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

NAME_TO_FILE = {
    "老大": "laoda.md",
    "老二": "laoer.md",
    "老三": "laosan.md",
    "老四": "laosi.md",
    "老五": "laowu.md",
    "老六": "laoliu.md",
    "老七": "laoqi.md",
    "老八": "laoba.md",
    "老九": "laojiu.md",
}


def load_prompt(name: str) -> str:
    path = os.path.join(PROMPT_DIR, NAME_TO_FILE[name])
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def create_all_agents() -> list[Agent]:
    return [Agent(name=name, system_prompt=load_prompt(name)) for name in AGENT_NAMES]


def create_agent(name: str) -> Agent:
    return Agent(name=name, system_prompt=load_prompt(name))
