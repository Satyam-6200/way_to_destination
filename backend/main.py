"""
Backend — accepts video chunks + GPS metadata, stores them PERSISTENTLY.

Storage:
  - Video chunks -> Supabase Storage (S3-compatible object storage)
  - Metadata     -> Postgres (Supabase-hosted)

This replaces the earlier SQLite + local-disk approach, which broke every
time Render's free-tier service redeployed or spun down (ephemeral
filesystem — Render's own docs confirm data is lost on redeploy, restart,
AND spin-down after 15 min idle). Postgres + object storage survive all of that.

Required environment variables (set these in Render's dashboard under
Environment — never commit real values to the repo):
  DATABASE_URL         - Postgres connection string (Supabase "Transaction
                          pooler" URI, e.g. postgresql://user:pass@host:6543/postgres)
  SUPABASE_URL          - e.g. https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY   - the "service_role" secret key (NOT the anon key)
"""

import json
import os
import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from supabase import create_client
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ["DATABASE_URL"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
VIDEO_BUCKET = "way to destination"

app = FastAPI(title="way_to_destination backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            chunk_index INTEGER NOT NULL,
            video_url TEXT NOT NULL,
            gps_points TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


init_db()


@app.post("/session/start")
def start_session():
    session_id = str(uuid.uuid4())
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (session_id, created_at) VALUES (%s, %s)",
        (session_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"session_id": session_id}


@app.post("/session/{session_id}/chunk")
async def upload_chunk(
    session_id: str,
    chunk_index: int = Form(...),
    gps_points: str = Form(...),
    video: UploadFile = File(...),
):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sessions WHERE session_id = %s", (session_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        parsed_points = json.loads(gps_points)
    except json.JSONDecodeError:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="gps_points must be valid JSON")

    content = await video.read()
    storage_path = f"{session_id}/chunk_{chunk_index}.webm"

    # Upload to Supabase Storage (persists across redeploys/restarts)
    supabase_client.storage.from_(VIDEO_BUCKET).upload(
        storage_path,
        content,
        {"content-type": "video/webm", "upsert": "true"},
    )
    video_url = supabase_client.storage.from_(VIDEO_BUCKET).get_public_url(storage_path)

    cur.execute(
        """INSERT INTO chunks (session_id, chunk_index, video_url, gps_points, created_at)
           VALUES (%s, %s, %s, %s, %s)""",
        (
            session_id,
            chunk_index,
            video_url,
            gps_points,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "status": "ok",
        "session_id": session_id,
        "chunk_index": chunk_index,
        "points_received": len(parsed_points),
        "video_size_bytes": len(content),
        "video_url": video_url,
    }


@app.get("/session/{session_id}")
def get_session(session_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
    session = cur.fetchone()
    if not session:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    cur.execute(
        "SELECT chunk_index, video_url, gps_points, created_at FROM chunks "
        "WHERE session_id = %s ORDER BY chunk_index",
        (session_id,),
    )
    chunks = cur.fetchall()
    cur.close()
    conn.close()

    return {
        "session_id": session_id,
        "created_at": session["created_at"],
        "chunks": [
            {
                "chunk_index": c["chunk_index"],
                "video_url": c["video_url"],
                "gps_points": json.loads(c["gps_points"]),
                "created_at": c["created_at"],
            }
            for c in chunks
        ],
    }


@app.get("/sessions")
def list_sessions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT session_id, created_at FROM sessions ORDER BY created_at DESC")
    sessions = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(s) for s in sessions]


@app.get("/geocode")
def geocode_point(lat: float, lng: float):
    import reverse_geocoder as rg
    result = rg.search([(lat, lng)])[0]
    return {
        "name": result["name"],
        "admin1": result["admin1"],
        "admin2": result["admin2"],
        "country_code": result["cc"],
    }


@app.post("/geocode/batch")
def geocode_batch(points: list[dict]):
    import reverse_geocoder as rg
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
