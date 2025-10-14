from fastapi import FastAPI, Depends, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import json, requests, os

from .db import get_db
from .agent.graph import run_agent

import asgi  # provided by Cloudflare runtime
from workers import WorkerEntrypoint, Response

load_dotenv()
FRONT_URL = os.getenv("FRONT_URL", "*")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONT_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/chat")
async def chat(websocket: WebSocket, db=Depends(get_db)):
    try:
        await websocket.accept()
        data = await websocket.receive_text()
        parsed = json.loads(data)
        query = parsed.get("query", "")
        response_text = ""

        async for message in run_agent(query):
            if not message.get("done"):
                await websocket.send_text(json.dumps(message))
            else:
                await websocket.send_text(json.dumps({"done": True}))
                await websocket.close()
                return
    except Exception as e:
        print("Error in websocket:", e)
        try:
            await websocket.send_text(json.dumps({"error": str(e), "done": True}))
            await websocket.close()
        except Exception:
            pass

@app.get("/ticker-list")
async def ticker_list():
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {
        "User-Agent": "Bob (bob@example.com)",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch SEC tickers")

    try:
        return resp.json()
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid JSON from SEC server")

# Cloudflare Worker entrypoint
class Default(WorkerEntrypoint):
    async def fetch(self, request, env, ctx):
        return await asgi.fetch(app, request, env)

# if __name__ == "__main__": run(app)