import uuid
from pathlib import Path

import chromadb

_STORAGE_DIR = Path(__file__).parent
_chroma = None

# ChromaDB collection names must be ASCII
_NAME_TO_COLLECTION = {
    "老大": "agent_laoda",
    "老二": "agent_laoer",
    "老三": "agent_laosan",
    "老四": "agent_laosi",
    "老五": "agent_laowu",
    "老六": "agent_laoliu",
    "老七": "agent_laoqi",
    "老八": "agent_laoba",
    "老九": "agent_laojiu",
}


def _client() -> chromadb.PersistentClient:
    global _chroma
    if _chroma is None:
        _chroma = chromadb.PersistentClient(path=str(_STORAGE_DIR))
    return _chroma


class AgentMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        col_name = _NAME_TO_COLLECTION.get(agent_name, f"agent_{agent_name}")
        self._col = _client().get_or_create_collection(
            name=col_name,
            metadata={"agent": agent_name},
        )

    def store(self, content: str, meta: dict | None = None) -> None:
        self._col.add(
            documents=[content],
            metadatas=[{"agent": self.agent_name, **(meta or {})}],
            ids=[str(uuid.uuid4())],
        )

    def query(self, query_text: str, n: int = 5) -> list[str]:
        total = self._col.count()
        if total == 0:
            return []
        result = self._col.query(
            query_texts=[query_text],
            n_results=min(n, total),
        )
        return result["documents"][0] if result["documents"] else []

    def get_recent(self, n: int = 20) -> list[dict]:
        result = self._col.get(include=["documents", "metadatas"])
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        items = [{"content": d, "meta": m} for d, m in zip(docs, metas)]
        return items[-n:]

    def count(self) -> int:
        return self._col.count()

    def clear(self) -> int:
        result = self._col.get()
        ids = result.get("ids") or []
        if ids:
            self._col.delete(ids=ids)
        return len(ids)
