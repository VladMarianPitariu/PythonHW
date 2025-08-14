from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os, json

# ---------- Storage ----------
DATA_DIR = os.getenv("LEADERBOARD_DIR", os.path.dirname(__file__))
LEADERBOARD_FILE = os.path.join(DATA_DIR, "leaderboard.json")

class Score(BaseModel):
    player: str
    score: int
    date: str

def load_leaderboard() -> List[dict]:
    if not os.path.exists(LEADERBOARD_FILE):
        return []
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def save_leaderboard(entries: List[dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(entries, f, indent=2)

# ---------- App ----------
app = FastAPI(title="Snake Leaderboard")

# Allow your game (and browsers) to fetch freely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache (simple)
leaderboard: List[dict] = load_leaderboard()

# ---------- API ----------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/scores/")
async def add_score(score: Score):
    global leaderboard
    entry = score.dict()
    leaderboard.append(entry)
    leaderboard.sort(key=lambda x: x["score"], reverse=True)
    save_leaderboard(leaderboard)
    return {"message": "Score added"}

@app.get("/leaderboard/", response_model=List[Score])
async def get_leaderboard(q: Optional[str] = Query(None, description="Filter by player name (case-insensitive)")):
    global leaderboard
    leaderboard = load_leaderboard()  # reload in case file changed
    entries = leaderboard
    if q:
        q_low = q.lower()
        entries = [e for e in leaderboard if q_low in e.get("player", "").lower()]
    return entries[:50]

@app.delete("/leaderboard/")
async def clear_leaderboard():
    global leaderboard
    leaderboard = []
    save_leaderboard(leaderboard)
    return {"message": "Leaderboard cleared"}

# ---------- Minimal UI ----------
UI_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Snake Leaderboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">
  <div class="max-w-5xl mx-auto px-4 py-8">
    <header class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold">Snake Leaderboard</h1>
      <a href="/health" target="_blank" class="text-sm underline text-slate-300 hover:text-white">API health</a>
    </header>

    <div class="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between mb-6">
      <div class="relative w-full sm:w-80">
        <input id="search" type="text" placeholder="Search by name..." class="w-full rounded-2xl bg-slate-800/70 border border-slate-700 px-4 py-2 outline-none focus:border-indigo-400" />
        <div class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">⌘K</div>
      </div>
      <div class="text-sm text-slate-400" id="count"></div>
    </div>

    <div id="cards" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"></div>
  </div>

  <template id="card-tpl">
    <div class="rounded-2xl bg-slate-800/70 border border-slate-700 shadow hover:shadow-lg transition">
      <div class="p-4 flex items-center justify-between">
        <div>
          <div class="text-lg font-semibold" data-name></div>
          <div class="text-xs text-slate-400" data-date></div>
        </div>
        <div class="text-2xl font-bold text-emerald-400" data-score></div>
      </div>
    </div>
  </template>

  <script>
    const API = new URL(window.location.origin);
    API.pathname = "/leaderboard/";

    const qs = new URLSearchParams(window.location.search);
    const initialQuery = qs.get("q") || "";
    const searchEl = document.getElementById("search");
    const cardsEl = document.getElementById("cards");
    const countEl = document.getElementById("count");
    const tpl = document.getElementById("card-tpl");

    searchEl.value = initialQuery;

    function debounce(fn, ms=250){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms);} }

    function render(list){
      cardsEl.innerHTML = "";
      list.forEach(entry => {
        const node = tpl.content.cloneNode(true);
        node.querySelector("[data-name]").textContent = entry.player ?? "—";
        node.querySelector("[data-date]").textContent = entry.date ? new Date(entry.date).toLocaleString() : "";
        node.querySelector("[data-score]").textContent = entry.score ?? 0;
        cardsEl.appendChild(node);
      });
      countEl.textContent = `${list.length} entr${list.length===1?'y':'ies'}`;
    }

    async function fetchData(q){
      const url = new URL(API);
      if (q) url.searchParams.set("q", q);
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch leaderboard");
      return await res.json();
    }

    const update = debounce(async () => {
      const q = searchEl.value.trim();
      const list = await fetchData(q);
      render(list);
      const url = new URL(window.location);
      if (q) url.searchParams.set("q", q); else url.searchParams.delete("q");
      window.history.replaceState({}, "", url);
    }, 200);

    // keyboard shortcut for quick focus
    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k"){
        e.preventDefault();
        searchEl.focus();
        searchEl.select();
      }
    });

    searchEl.addEventListener("input", update);
    // initial load
    update();
  </script>
</body>
</html>
"""

@app.get("/ui", response_class=HTMLResponse)
def ui():
    return HTMLResponse(content=UI_HTML, status_code=200)
