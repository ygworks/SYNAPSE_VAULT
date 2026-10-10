import os
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from vault.stream import router as stream_router
from canvas.router import router as canvas_router
from brain.router import router as brain_router

app = FastAPI(title="SYNAPSE VAULT", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream_router)
app.include_router(canvas_router)
app.include_router(brain_router)

static_path = os.path.join(os.path.dirname(__file__), "canvas/static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(static_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "ok", "message": "SYNAPSE VAULT 엔진 구동 중"}

if __name__ == "__main__":
    print("=" * 60)
    print("🏛️  PROJECT SYNAPSE VAULT 온라인")
    print("🖥️  접속 URL: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
