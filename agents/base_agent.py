import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

AGENT_NAMES = ["老大", "老二", "老三", "老四", "老五", "老六", "老七", "老八", "老九"]

_client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


class Agent:
    def __init__(self, name: str, system_prompt: str):
        if name not in AGENT_NAMES:
            raise ValueError(f"Unknown agent name: {name}. Must be one of {AGENT_NAMES}")

        self.name = name
        self.system_prompt = system_prompt
        self.alive = True
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

        index = AGENT_NAMES.index(name) + 1
        model_key = f"AGENT_{index}_MODEL"
        self.model = os.getenv(model_key)
        if not self.model:
            raise ValueError(f"Model not set for {name}: add {model_key}=<model> to .env")

        from memory.agent_memory import AgentMemory
        self.memory = AgentMemory(name)

    def reset_messages(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]
