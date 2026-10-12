"""Read-only HTTP API and deterministic SSE stream tests."""
import asyncio
import json

from fastapi.testclient import TestClient

from ios_poll.storage import PollStore
from ios_poll.web import create_app, iter_sse


def test_dashboard_and_api(tmp_path):
    path = tmp_path / "poll.sqlite3"
    app = create_app(path)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        empty = client.get("/api/results")
        assert empty.status_code == 200
        assert empty.headers["cache-control"] == "no-store"
        assert empty.json()["status"] == "WAITING"
        assert empty.json()["total"] == 0

        store = app.state.store
        session = store.start()
        store.cast(session, 101, "ios")
        store.cast(session, 102, "android")
        store.cast(session, 103, "other")
        results = client.get("/api/results").json()
        assert results["status"] == "OPEN"
        assert results["total"] == 3
        assert results["results"]["other"]["votes"] == 1
        assert "telegram_user_id" not in json.dumps(results)
        assert "101" not in json.dumps(results)
        assert client.get("/api/poll").json()["status"] == "OPEN"

        page = client.get("/screen")
        assert page.status_code == 200
        assert "будущие программисты" in page.text
        assert "/static/screen.js" in page.text
        assert client.get("/static/screen.js").status_code == 200
        assert client.get("/static/screen.css").status_code == 200
        assert client.post("/api/results").status_code in (404, 405)
        assert client.post("/api/vote").status_code in (404, 405)

        store.close()
        assert client.get("/api/results").json()["status"] == "CLOSED"


def test_sse_sends_initial_changes_and_close(tmp_path):
    store = PollStore(tmp_path / "poll.sqlite3")
    store.init()

    class ScriptedRequest:
        calls = 0

        async def is_disconnected(self):
            self.calls += 1
            if self.calls == 2:
                self.session = store.start()
            if self.calls == 3:
                store.cast(self.session, 25, "ios")
            if self.calls == 4:
                store.close()
            return self.calls > 4

    async def collect():
        request = ScriptedRequest()
        return [event async for event in iter_sse(request, store, poll_interval=0)]

    events = asyncio.run(collect())
    assert len(events) == 4
    assert [event.split("\n", 1)[0] for event in events] == [
        "event: results_updated",
        "event: results_updated",
        "event: results_updated",
        "event: poll_closed",
    ]
    payloads = [json.loads(event.split("data: ", 1)[1]) for event in events]
    assert [p["status"] for p in payloads] == ["WAITING", "OPEN", "OPEN", "CLOSED"]
    assert payloads[-1]["total"] == 1
    assert payloads[-1]["results"]["ios"]["votes"] == 1


def test_sse_heartbeat_without_changes(tmp_path):
    store = PollStore(tmp_path / "poll.sqlite3")
    store.init()

    class Request:
        calls = 0

        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 2

    async def collect():
        return [event async for event in iter_sse(Request(), store, poll_interval=0, heartbeat_seconds=-1)]

    events = asyncio.run(collect())
    assert events[0].startswith("event: results_updated")
    assert events[1] == ": heartbeat\n\n"
