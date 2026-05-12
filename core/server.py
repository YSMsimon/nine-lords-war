import asyncio
import contextlib
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from core.bridge import GameBridge
from agents.base_agent import AGENT_NAMES


def json_utf8(data) -> Response:
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
    )


bridge = GameBridge()
app = FastAPI()
_game_task: asyncio.Task | None = None

DASHBOARD = Path(__file__).parent.parent / "dashboard" / "index.html"


async def _start_game() -> None:
    global _game_task
    from agents.agent_factory import create_all_agents
    from rounds.round_manager import run_game
    from memory.agent_memory import AgentMemory

    # Cancel the running game if any
    if _game_task and not _game_task.done():
        _game_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _game_task

    # Wipe all agent memories
    for name in AGENT_NAMES:
        AgentMemory(name).clear()

    # Reset all bridge state
    bridge.reset()
    await bridge.broadcast({"type": "game_restart"})

    agents = create_all_agents()
    bridge.agents = agents
    _game_task = asyncio.create_task(run_game(agents, bridge))


@app.get("/")
async def index():
    return FileResponse(DASHBOARD)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await bridge.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            cmd_type = data.get("type")

            # ── instant king actions (no queue) ──────────────────────────

            if cmd_type == "king_speak":
                content = data.get("content", "").strip()
                if content:
                    bridge.add_king_message(content)
                    await bridge.broadcast({"type": "king_speak", "content": content})
                    from rounds.round_manager import king_address_all
                    asyncio.create_task(king_address_all(content, bridge))

            elif cmd_type == "king_at":
                target = data.get("target", "").strip()
                content = data.get("content", "").strip()
                if target and content:
                    bridge.add_king_message(f"@{target}：{content}")
                    await bridge.broadcast({"type": "king_speak", "content": f"@{target}：{content}"})
                    from rounds.round_manager import king_at_agent
                    asyncio.create_task(king_at_agent(target, content, bridge))

            elif cmd_type == "king_execute":
                target = data.get("target")
                for a in bridge.agents:
                    if a.name == target and a.alive:
                        a.alive = False
                        await bridge.broadcast({"type": "eliminated", "target": target})
                        break
                alive = [a for a in bridge.agents if a.alive]
                if len(alive) == 0:
                    await bridge.broadcast({"type": "game_over", "champion": "皇上"})
                elif len(alive) == 1:
                    await bridge.broadcast({"type": "game_over", "champion": alive[0].name})

            elif cmd_type == "king_proceed":
                bridge.king_proceed.set()

            elif cmd_type == "king_end_game":
                bridge.king_end.set()

            elif cmd_type == "restart_game":
                asyncio.create_task(_start_game())

            # ── king_question only accepted while backend is waiting for one ─
            elif cmd_type == "king_question":
                if bridge.accepting_question:
                    await bridge.queue_command(data)

            # ── data-carrying commands → queue ────────────────────────────
            else:
                await bridge.queue_command(data)

    except WebSocketDisconnect:
        bridge.disconnect(ws)
    except Exception:
        bridge.disconnect(ws)


@app.get("/api/memory/{agent_name}")
async def get_memory(agent_name: str):
    from memory.agent_memory import AgentMemory
    mem = AgentMemory(agent_name)
    return json_utf8({
        "agent": agent_name,
        "total": mem.count(),
        "recent": mem.get_recent(30),
    })


@app.get("/api/memory")
async def get_all_memory():
    from memory.agent_memory import AgentMemory
    return json_utf8({
        name: {"total": AgentMemory(name).count()}
        for name in AGENT_NAMES
    })


@app.delete("/api/memory/{agent_name}")
async def delete_agent_memory(agent_name: str):
    from memory.agent_memory import AgentMemory
    deleted = AgentMemory(agent_name).clear()
    return json_utf8({"agent": agent_name, "deleted": deleted})


@app.delete("/api/memory")
async def delete_all_memory():
    from memory.agent_memory import AgentMemory
    return json_utf8({
        "deleted": {name: AgentMemory(name).clear() for name in AGENT_NAMES}
    })


@app.on_event("startup")
async def startup():
    await _start_game()
