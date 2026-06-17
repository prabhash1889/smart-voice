from datetime import datetime, timezone

from smartvoice.core.models import WorkflowResult
from smartvoice.storage.history_store import HistoryStore


def test_history_save_and_recent(tmp_path):
    store = HistoryStore(db_path=tmp_path / "history.sqlite3", limit=2)

    store.save(WorkflowResult(mode="raw_transcript", raw_text="a", final_text="a", created_at=datetime.now(timezone.utc)))
    store.save(WorkflowResult(mode="raw_transcript", raw_text="b", final_text="b", created_at=datetime.now(timezone.utc)))

    rows = store.recent()

    assert len(rows) == 2
    assert rows[0]["final_text"] == "b"


def test_history_latest_success_and_clear(tmp_path):
    store = HistoryStore(db_path=tmp_path / "history.sqlite3", limit=10)
    store.save(WorkflowResult(mode="raw_transcript", raw_text="", final_text="", error="failed", created_at=datetime.now(timezone.utc)))
    store.save(WorkflowResult(mode="raw_transcript", raw_text="ok", final_text="ok", created_at=datetime.now(timezone.utc)))

    assert store.latest_success()["final_text"] == "ok"

    store.clear()

    assert store.recent() == []
