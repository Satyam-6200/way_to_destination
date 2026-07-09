"""
Phase 2 backend — accepts video chunks + GPS metadata, stores them.

Each recording session has a unique session_id (generated client-side or
server-side). Video is uploaded in small chunks (e.g. every 5-10 seconds)
along with the GPS points captured during that chunk's time window.

Storage (for now, local dev):
  - Video chunks -> backend/uploads/{session_id}/chunk_{index}.webm
  - Metadata     -> SQLite db (backend/data.db)

Later (Phase 3+) this moves to S3-compatible storage + Postgres/PostGIS,
but SQLite + local disk is enough to prove the upload flow works.
"""

import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone

import reverse_geocoder as rg
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "data.db"

UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="way_to_destination backend")

# Allow requests from the frontend (GitHub Pages, local dev, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            video_path TEXT NOT NULL,
            gps_points TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)
    conn.commit()
    conn.close()


init_db()


@app.post("/session/start")
def start_session():
    """Call this once when the user hits 'Start Recording'."""
    session_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, created_at) VALUES (?, ?)",
        (session_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return {"session_id": session_id}


@app.post("/session/{session_id}/chunk")
async def upload_chunk(
    session_id: str,
    chunk_index: int = Form(...),
    gps_points: str = Form(...),  # JSON string: [{t, lat, lng, accuracy}, ...]
    video: UploadFile = File(...),
):
    """Upload one video chunk + the GPS points captured during it."""
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        parsed_points = json.loads(gps_points)
    except json.JSONDecodeError:
        conn.close()
        raise HTTPException(status_code=400, detail="gps_points must be valid JSON")

    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    video_path = session_dir / f"chunk_{chunk_index}.webm"

    content = await video.read()
    video_path.write_bytes(content)

    conn.execute(
        """INSERT INTO chunks (session_id, chunk_index, video_path, gps_points, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            session_id,
            chunk_index,
            str(video_path.relative_to(BASE_DIR)),
            gps_points,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "session_id": session_id,
        "chunk_index": chunk_index,
        "points_received": len(parsed_points),
        "video_size_bytes": len(content),
    }


@app.get("/session/{session_id}")
def get_session(session_id: str):
    """Fetch all chunks + GPS trail for a session (used later to render on map)."""
    conn = get_db()
    session = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    chunks = conn.execute(
        "SELECT chunk_index, video_path, gps_points, created_at FROM chunks "
        "WHERE session_id = ? ORDER BY chunk_index",
        (session_id,),
    ).fetchall()
    conn.close()

    return {
        "session_id": session_id,
        "created_at": session["created_at"],
        "chunks": [
            {
                "chunk_index": c["chunk_index"],
                "video_path": c["video_path"],
                "gps_points": json.loads(c["gps_points"]),
                "created_at": c["created_at"],
            }
            for c in chunks
        ],
    }


@app.get("/sessions")
def list_sessions():
    """List all recorded sessions (for the map view later)."""
    conn = get_db()
    sessions = conn.execute(
        "SELECT session_id, created_at FROM sessions ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(s) for s in sessions]


@app.get("/session/{session_id}/chunk/{chunk_index}/video")
def get_chunk_video(session_id: str, chunk_index: int):
    """Serve the actual video file for one chunk (used for click-to-seek playback)."""
    conn = get_db()
    chunk = conn.execute(
        "SELECT video_path FROM chunks WHERE session_id = ? AND chunk_index = ?",
        (session_id, chunk_index),
    ).fetchone()
    conn.close()

    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    video_path = BASE_DIR / chunk["video_path"]
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")

    return FileResponse(video_path, media_type="video/webm")


@app.get("/geocode")
def geocode_point(lat: float, lng: float):
    """Reverse geocode a single coordinate to a place name using offline
    GeoNames data (no external API call)."""
    result = rg.search([(lat, lng)])[0]
    return {
        "name": result["name"],
        "admin1": result["admin1"],  # state/province
        "admin2": result["admin2"],  # district/county
        "country_code": result["cc"],
    }


@app.post("/geocode/batch")
def geocode_batch(points: list[dict]):
    """Reverse geocode multiple coordinates at once (more efficient than
    calling /geocode in a loop). Body: [{"lat": .., "lng": ..}, ...]"""
    coords = [(p["lat"], p["lng"]) for p in points]
    if not coords:
        return []
    results = rg.search(coords)
    return [
        {
            "name": r["name"],
            "admin1": r["admin1"],
            "admin2": r["admin2"],
            "country_code": r["cc"],
        }
        for r in results
    ]


@app.get("/health")
def health():
    return {"status": "ok"}
