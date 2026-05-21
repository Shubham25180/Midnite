# Skynet/ui/server.py
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from Skynet.core.runtime_manager import RuntimeManager

from Skynet.ui.ws.stream import EventStreamBroadcaster

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def build_app(manager: RuntimeManager, server_holder: list | None = None) -> FastAPI:
    broadcaster = EventStreamBroadcaster(manager.bus)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        broadcaster.start()
        yield
        broadcaster.stop()

    app = FastAPI(title="Nexux Dashboard", lifespan=lifespan)

    from Skynet.ui.routes import settings as settings_mod, hardware, status, models
    from Skynet.ui.routes import voices as voices_mod
    app.include_router(settings_mod.make_router(manager))
    app.include_router(settings_mod.make_debug_router(manager))
    app.include_router(settings_mod.make_mic_router(manager))
    app.include_router(settings_mod.make_stt_router(manager))
    app.include_router(settings_mod.make_tools_router(manager))
    app.include_router(settings_mod.make_llm2_router(manager))
    app.include_router(voices_mod.make_voice_router(manager))
    app.include_router(hardware.router)
    app.include_router(status.router)
    app.include_router(models.router)

    @app.websocket("/ws/stream")
    async def ws_stream(ws: WebSocket) -> None:
        await ws.accept()
        q = broadcaster.add_client()
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    # Keepalive ping — client ignores unknown types
                    await ws.send_text('{"type":"ping"}')
                    continue
                await ws.send_text(json.dumps(msg))
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.remove_client(q)

    @app.get("/api/status")
    async def get_status():
        return {
            "runtime_mode": manager.state.runtime_mode.name.lower(),
            "components": {
                name: manager.state.get_component_state(name).name.lower()
                for name in manager.registry.components
            },
        }

    @app.post("/api/runtime/initialize")
    async def api_initialize():
        asyncio.create_task(manager.initialize())
        return {"status": "initializing"}

    @app.post("/api/runtime/shutdown")
    async def api_shutdown():
        async def _do_shutdown():
            await manager.shutdown()
            # Signal uvicorn to exit after all components stop cleanly
            if server_holder:
                server_holder[0].should_exit = True
        asyncio.create_task(_do_shutdown())
        return {"status": "shutting_down"}

    @app.post("/api/chat/send")
    async def api_chat_send(data: dict):
        text = (data.get("text") or "").strip()
        if not text:
            return {"error": "empty text"}
        from Skynet.core.events import STTTranscribedEvent
        manager.bus.publish(STTTranscribedEvent(transcript=text))
        return {"status": "sent", "text": text}

    @app.post("/api/stt/ptt/start")
    async def api_ptt_start():
        stt = manager.get_component("audio_device")
        if stt is not None and hasattr(stt, "start_ptt"):
            stt.start_ptt()
        return {"status": "recording"}

    @app.post("/api/stt/ptt/stop")
    async def api_ptt_stop():
        stt = manager.get_component("audio_device")
        if stt is not None and hasattr(stt, "stop_ptt"):
            stt.stop_ptt()
        return {"status": "processing"}

    @app.post("/api/tts/test")
    async def api_tts_test(text: str = "Hello. I am Nexux, your AI companion. How can I help you today?"):
        from Skynet.core.events import OrchestratorResponseEvent
        manager.bus.publish(OrchestratorResponseEvent(response=text))
        return {"status": "fired", "text": text}

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


def start_server(manager: RuntimeManager, host: str = "127.0.0.1", port: int = 7799) -> None:
    server_holder: list = []
    app = build_app(manager, server_holder=server_holder)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_holder.append(server)
    server.run()
