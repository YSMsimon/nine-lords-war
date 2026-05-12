import asyncio
import json
from fastapi import WebSocket

MAX_FEED_LOG = 300


class GameBridge:
    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._cmd_queue: asyncio.Queue = asyncio.Queue()
        self._king_messages: list[str] = []
        self.agents = []

        self.king_proceed = asyncio.Event()
        self.king_end = asyncio.Event()

        # ── State tracked for reconnect sync ──────────────────────────────
        self.current_round: int = 0
        self.current_phase: str = ""
        self._alliance_pairs: list[tuple[str, str]] = []
        self.accepting_question: bool = False
        self._feed_log: list[dict] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)
        if self.agents and self.current_round > 0:
            alive = [a.name for a in self.agents if a.alive]
            all_agents = [a.name for a in self.agents]
            await ws.send_text(json.dumps({
                "type": "state_sync",
                "round": self.current_round,
                "phase": self.current_phase,
                "alive": alive,
                "all_agents": all_agents,
                "alliances": [list(p) for p in self._alliance_pairs],
                "feed_log": self._feed_log,
                "accepting_question": self.accepting_question,
            }, ensure_ascii=False))

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    def reset(self) -> None:
        self.current_round = 0
        self.current_phase = ""
        self._alliance_pairs = []
        self.accepting_question = False
        self._feed_log = []
        self._king_messages = []
        self.king_proceed.clear()
        self.king_end.clear()
        self.drain_queue()
        self.agents = []

    def _make_feed_entry(self, event: dict) -> dict | None:
        t = event.get("type")
        if t == "speak":
            return {"kind": "speak", "agent": event.get("agent"),
                    "content": event.get("content"), "phase": event.get("phase")}
        if t == "king_speak":
            return {"kind": "king_speak", "content": event.get("content")}
        if t == "question":
            return {"kind": "question", "content": event.get("content")}
        if t == "votes":
            return {"kind": "votes", "votes": event.get("votes", {})}
        if t == "alliance_proposal":
            return {"kind": "alliance_proposal", "from": event.get("from"),
                    "to": event.get("to"), "reason": event.get("reason")}
        if t == "alliance_decision":
            return {"kind": "alliance_decision", "action": event.get("action"),
                    "agent": event.get("agent"), "partner": event.get("partner")}
        if t == "private_message":
            return {"kind": "private_message", "from": event.get("from"),
                    "to": event.get("to"), "message": event.get("message")}
        if t == "eliminated":
            return {"kind": "eliminated", "target": event.get("target")}
        if t == "saved":
            return {"kind": "saved", "target": event.get("target")}
        if t == "king_action":
            return {"kind": "king_action", "action": event.get("action"),
                    "target": event.get("target")}
        if t == "round_start":
            return {"kind": "round_start", "round": event.get("round"),
                    "alive": event.get("alive", [])}
        if t == "phase":
            return {"kind": "phase", "phase": event.get("phase")}
        if t == "game_start":
            return {"kind": "game_start", "agents": event.get("agents", [])}
        if t == "game_over":
            return {"kind": "game_over", "champion": event.get("champion")}
        return None

    async def broadcast(self, event: dict):
        # Track state for reconnect sync
        t = event.get("type")
        if t == "round_start":
            self.current_round = event.get("round", self.current_round)
            self.current_phase = ""
        elif t == "phase":
            self.current_phase = event.get("phase", self.current_phase)
        elif t == "eliminated":
            target = event.get("target")
            if target:
                self._alliance_pairs = [
                    p for p in self._alliance_pairs if target not in p
                ]
        elif t == "alliance_decision":
            agent = event.get("agent", "")
            partner = event.get("partner", "")
            action = event.get("action", "")
            pair_set = {agent, partner}
            if action == "accept":
                if not any(set(p) == pair_set for p in self._alliance_pairs):
                    self._alliance_pairs.append((agent, partner))
            elif action == "breakup":
                self._alliance_pairs = [
                    p for p in self._alliance_pairs if set(p) != pair_set
                ]

        # Append to feed log
        entry = self._make_feed_entry(event)
        if entry is not None:
            self._feed_log.append(entry)
            if len(self._feed_log) > MAX_FEED_LOG:
                self._feed_log.pop(0)

        msg = json.dumps(event, ensure_ascii=False)
        dead = set()
        for c in self._clients:
            try:
                await c.send_text(msg)
            except Exception:
                dead.add(c)
        self._clients -= dead

    def add_king_message(self, content: str):
        self._king_messages.append(content)
        if len(self._king_messages) > 10:
            self._king_messages.pop(0)

    def get_king_context(self) -> str:
        if not self._king_messages:
            return ""
        msgs = "\n".join(f"【皇上】{m}" for m in self._king_messages[-3:])
        return f"\n\n皇上近期旨意：\n{msgs}"

    # ── queue for data-carrying commands (king_question, king_save, etc.) ──

    async def queue_command(self, cmd: dict):
        await self._cmd_queue.put(cmd)

    async def next_command(self, timeout: float | None = None) -> dict | None:
        if timeout is None:
            return await self._cmd_queue.get()
        try:
            return await asyncio.wait_for(asyncio.shield(self._cmd_queue.get()), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def drain_queue(self):
        while not self._cmd_queue.empty():
            try:
                self._cmd_queue.get_nowait()
            except Exception:
                break

    # ── king phase gate ───────────────────────────────────────────────────

    async def wait_for_king_proceed(self, phase_label: str) -> bool:
        if self.king_proceed.is_set():
            self.king_proceed.clear()
            return True

        await self.broadcast({"type": "await_king", "phase": phase_label})

        proceed_task = asyncio.create_task(self.king_proceed.wait())
        end_task = asyncio.create_task(self.king_end.wait())

        done, pending = await asyncio.wait(
            [proceed_task, end_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()

        if self.king_end.is_set():
            self.king_end.clear()
            return False

        self.king_proceed.clear()
        return True
