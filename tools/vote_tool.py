from agents.base_agent import Agent
from tools.base_tool import BaseTool


class VoteTool(BaseTool):
    def __init__(self, agent: Agent):
        super().__init__(
            agent=agent,
            name="vote",
            description=f"Vote to eliminate a prince (used by {agent.name})",
        )

    def get_schema(self) -> list:
        return [
            {
                "type": "function",
                "function": {
                    "name": "vote",
                    "description": (
                        f"You are {self.agent.name}. Vote to eliminate one prince. "
                        "You cannot vote for yourself."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "The name of the prince you want to eliminate",
                            },
                        },
                        "required": ["target"],
                    },
                },
            }
        ]

    def run(self, **kwargs) -> str:
        return f"[投票] {self.agent.name} 投票淘汰 {kwargs['target']}"
