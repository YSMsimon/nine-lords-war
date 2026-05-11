from agents.base_agent import Agent
from tools.base_tool import BaseTool


class AttackTool(BaseTool):
    def __init__(self, agent: Agent):
        super().__init__(
            agent=agent,
            name="attack",
            description=f"Attack another prince's proposal (used by {agent.name})",
        )

    def get_schema(self) -> list:
        return [
            {
                "type": "function",
                "function": {
                    "name": "attack",
                    "description": (
                        f"You are {self.agent.name}. Attack another prince by pointing out "
                        "the flaws or weaknesses in their proposal."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "The name of the prince you are attacking",
                            },
                            "content": {
                                "type": "string",
                                "description": "Your attack argument against the target's proposal",
                            },
                        },
                        "required": ["target", "content"],
                    },
                },
            }
        ]

    def run(self, **kwargs) -> str:
        target = kwargs["target"]
        content = kwargs["content"]
        return f"[攻击] {self.agent.name} → {target}: {content}"
