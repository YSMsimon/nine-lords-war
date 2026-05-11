import os
import asyncio
from dotenv import load_dotenv
import litellm

load_dotenv()

AGENT_NAMES = ["老大", "老二", "老三", "老四", "老五", "老六", "老七", "老八", "老九"]


class Agent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.alive = True
        self.score = 0
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

        index = AGENT_NAMES.index(name) + 1
        model_key = f"AGENT_{index}_MODEL"
        self.model = os.getenv(model_key)
        if not self.model:
            raise ValueError(f"Model not set for {name}: add {model_key}=<model> to .env")

    async def execute(self, user_message: str, tools: list | None = None) -> str:
        self.messages.append({"role": "user", "content": user_message})

        kwargs: dict = {"model": self.model, "messages": self.messages}
        if tools:
            kwargs["tools"] = tools

        response = await litellm.acompletion(**kwargs)

        reply = response.choices[0].message.content or ""
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def reset_messages(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
