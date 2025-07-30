
import json
import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from datetime import datetime


app = FastAPI()

# Persistent leaderboard storage
LEADERBOARD_FILE = os.path.join(os.path.dirname(__file__), 'leaderboard.json')

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, 'r') as f:
            data = json.load(f)
            # Convert date strings to datetime
            for entry in data:
                entry['date'] = datetime.fromisoformat(entry['date'])
            return data
    return []

def save_leaderboard(data):
    # Convert datetime to isoformat for JSON
    serializable = [dict(entry, date=entry['date'].isoformat() if isinstance(entry['date'], datetime) else entry['date']) for entry in data]
    with open(LEADERBOARD_FILE, 'w') as f:
        json.dump(serializable, f, indent=2)

leaderboard = load_leaderboard()

class Score(BaseModel):
    player: str
    score: int
    date: datetime


@app.post("/scores/")
async def add_score(score: Score):
    entry = score.dict()
    leaderboard.append(entry)
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    save_leaderboard(leaderboard)
    return {"message": "Score added"}


@app.get("/leaderboard/", response_model=List[Score])
async def get_leaderboard():
    # Always reload in case file changed
    global leaderboard
    leaderboard = load_leaderboard()
    return leaderboard[:10]