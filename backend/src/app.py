from fastapi import FastAPI, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .db import get_db
import json
from .agent.graph import run_agent
import requests
import os
from dotenv import load_dotenv

load_dotenv()
FRONT_URL = os.environ["FRONT_URL"]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONT_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/chat")
async def chat(websocket: WebSocket, db = Depends(get_db)):
    try:
        await websocket.accept()
        data = await websocket.receive_text()
        parsed_data = json.loads(data)
        query = parsed_data.get("query", "")
        response_text = ""

        async for message in run_agent(query):
            if not message["done"]:
                print(message)
                if "response" in message:
                    response_text += message["response"]
                    await websocket.send_text(json.dumps(message))
                else:
                    await websocket.send_text(json.dumps(message))
            else:
                await websocket.send_text(json.dumps({"done": True}))
                await websocket.close()
                return
    except Exception as e:
        print("Error in websocket: ", e)
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
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch SEC tickers")

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid JSON from SEC server")

    return data