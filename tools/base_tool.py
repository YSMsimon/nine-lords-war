from abc import ABC, abstractmethod
from agents.base_agent import Agent


class BaseTool(ABC):
    def __init__(self, agent: Agent, name: str, description: str):
        self.agent = agent
        self.name = name
        self.description = description

    @abstractmethod
    def get_schema(self) -> list:
        ...

    @abstractmethod
    def run(self, **kwargs) -> str | dict:
        ...
