import asyncio
from agents.agent_factory import create_all_agents
from rounds.round_manager import run_game


async def main():
    agents = create_all_agents()
    await run_game(agents)


if __name__ == "__main__":
    asyncio.run(main())
