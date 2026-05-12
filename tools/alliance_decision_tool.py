from agents.base_agent import Agent
from tools.base_tool import BaseTool


class AllianceDecisionTool(BaseTool):
    def __init__(self, agent: Agent):
        super().__init__(
            agent=agent,
            name="alliance_decision",
            description=f"Accept/reject an alliance proposal or break an existing alliance (used by {agent.name})",
        )

    def get_schema(self) -> list:
        return [
            {
                "type": "function",
                "function": {
                    "name": "alliance_decision",
                    "description": (
                        f"You are {self.agent.name}. Use this to respond to an incoming alliance proposal "
                        f"(accept=true to join, accept=false to reject) OR to proactively break an existing "
                        f"alliance (accept=false)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "partner": {
                                "type": "string",
                                "description": "The name of the prince you are making a decision about",
                            },
                            "action": {
                                "type": "string",
                                "enum": ["accept", "reject", "breakup"],
                                "description": (
                                    "'accept' to form an alliance, "
                                    "'reject' to turn down a proposal that was never accepted, "
                                    "'breakup' to dissolve an existing alliance"
                                ),
                            },
                            "reason": {
                                "type": "string",
                                "description": "Your reason for this decision",
                            },
                        },
                        "required": ["partner", "action", "reason"],
                    },
                },
            }
        ]

    def run(self, **kwargs) -> str:
        partner = kwargs["partner"]
        action = kwargs["action"]
        reason = kwargs["reason"]
        if action == "accept":
            return f"[结盟] {self.agent.name} 与 {partner} 结为同盟：{reason}"
        if action == "reject":
            return f"[拒绝] {self.agent.name} 拒绝了 {partner} 的结盟提议：{reason}"
        return f"[解盟] {self.agent.name} 与 {partner} 断绝同盟关系：{reason}"
