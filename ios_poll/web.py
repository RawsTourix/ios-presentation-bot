"""Read-only polling dashboard and realtime Server-Sent Events."""
import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .storage import PollStore

STATIC_DIR = Path(__file__).with_name("static")


async def iter_sse(
    request: Request,
    store: PollStore,
    poll_interval: float = 0.75,
    heartbeat_seconds: float = 15.0,
) -> AsyncIterator[str]:
    """Send full snapshots on changes; tolerate reconnects and new sessions."""
    last_revision = None
    last_emit = time.monotonic()
    while not await request.is_disconnected():
        snapshot = store.snapshot()
        revision = (snapshot["session_id"], snapshot["version"])
        if revision != last_revision:
            event = "poll_closed" if snapshot["status"] == "CLOSED" else "results_updated"
            yield "event: " + event + "\ndata: " + json.dumps(snapshot, ensure_ascii=False) + "\n\n"
            last_revision = revision
            last_emit = time.monotonic()
        elif time.monotonic() - last_emit >= heartbeat_seconds:
            yield ": heartbeat\n\n"
            last_emit = time.monotonic()
        await asyncio.sleep(poll_interval)


def create_app(database_path: str | Path | None = None, poll_interval: float = 0.75) -> FastAPI:
    path = Path(database_path or os.environ.get("DATABASE_PATH", "./data/poll.sqlite3"))
    store = PollStore(path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.init()
        yield

    application = FastAPI(
        title="iOS Presentation Poll",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.state.store = store
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/health")
    def health():
        # A successful read verifies that the shared SQLite database is accessible.
        store.snapshot()
        return {"status": "ok"}

    @application.get("/api/poll")
    def poll():
        state = store.snapshot()
        return JSONResponse(
            {key: state[key] for key in ("session_id", "status", "version", "total")},
            headers={"Cache-Control": "no-store"},
        )

    @application.get("/api/results")
    def results():
        return JSONResponse(store.snapshot(), headers={"Cache-Control": "no-store"})

    @application.get("/api/events")
    async def events(request: Request):
        return StreamingResponse(
            iter_sse(request, store, poll_interval=poll_interval),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    @application.get("/screen", include_in_schema=False)
    def screen():
        return FileResponse(
            STATIC_DIR / "index.html",
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    return application


app = create_app()
