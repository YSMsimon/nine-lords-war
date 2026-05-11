from agents.base_agent import Agent
from tools.base_tool import BaseTool


class PrivateMessageTool(BaseTool):
    def __init__(self, agent: Agent):
        super().__init__(
            agent=agent,
            name="private_message",
            description=f"Send a private message to another prince (used by {agent.name})",
        )

    def get_schema(self) -> list:
        return [
            {
                "type": "function",
                "function": {
                    "name": "private_message",
                    "description": (
                        f"You are {self.agent.name}. Send a secret private message "
                        "to another prince. Only they will see it."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "The name of the prince to message",
                            },
                            "message": {
                                "type": "string",
                                "description": "The private message content",
                            },
                        },
                        "required": ["target", "message"],
                    },
                },
            }
        ]

    def run(self, **kwargs) -> str:
        target = kwargs["target"]
        message = kwargs["message"]
        return f"[私信] {self.agent.name} → {target}: {message}"
