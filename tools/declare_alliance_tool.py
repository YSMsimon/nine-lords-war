from agents.base_agent import Agent
from tools.base_tool import BaseTool


class DeclareAllianceTool(BaseTool):
    def __init__(self, agent: Agent):
        super().__init__(
            agent=agent,
            name="declare_alliance",
            description=f"Declare an alliance with another prince (used by {agent.name})",
        )

    def get_schema(self) -> list:
        return [
            {
                "type": "function",
                "function": {
                    "name": "declare_alliance",
                    "description": (
                        f"You are {self.agent.name}. Propose an alliance with another prince. "
                        "Allies agree not to vote for each other and may coordinate strategy."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "The name of the prince you want to ally with",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Your reason for proposing this alliance",
                            },
                        },
                        "required": ["target", "reason"],
                    },
                },
            }
        ]

    def run(self, **kwargs) -> str:
        target = kwargs["target"]
        reason = kwargs["reason"]
        return f"[结盟] {self.agent.name} → {target}: {reason}"
