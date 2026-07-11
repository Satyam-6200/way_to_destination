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

import csv
import gzip
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from scipy.spatial import cKDTree
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


BASE_DIR = Path(__file__).parent


def _load_geonames_index():
    """GeoNames cities1000 (~200 India entries) — used as a fallback for
    points outside India, where we don't have the granular dataset."""
    import reverse_geocoder as rg
    csv_path = os.path.join(os.path.dirname(rg.__file__), "rg_cities1000.csv")
    places = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            places.append({
                "name": row["name"],
                "admin1": row["admin1"],
                "admin2": row["admin2"],
                "cc": row["cc"],
                "lat": float(row["lat"]),
                "lng": float(row["lon"]),
                "_name_lower": row["name"].lower(),
            })
    return places


def _load_india_index():
    """India Post's post-office directory (MIT-licensed, bundled locally as
    data/india_places.json.gz) — 150,000+ locations covering villages and
    hamlets, not just big towns. This is what actually fixes the accuracy
    problem GeoNames cities1000 had for rural India (e.g. returning
    "Bariarpur, Munger" for a point that's really in Jhanjhra, Khagaria)."""
    gz_path = BASE_DIR / "data" / "india_places.json.gz"
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        raw = json.load(f)

    places = []
    for row in raw:
        lat, lng = row.get("a"), row.get("n")
        if lat is None or lng is None:
            continue
        raw_name = row.get("o", "")
        # Dataset has inconsistent suffixes: "X B.O", "X BO", "X S.O" etc
        # (Branch/Sub/Head post office) — strip them for a cleaner display name
        clean_name = re.sub(r"\s+[BSH]\.?O\.?$", "", raw_name).strip()
        places.append({
            "name": clean_name or raw_name,
            "admin1": row.get("s", ""),   # state
            "admin2": row.get("i", ""),   # district
            "cc": "IN",
            "lat": float(lat),
            "lng": float(lng),
            "_name_lower": clean_name.lower() or raw_name.lower(),
        })
    return places


GEONAMES_INDEX = _load_geonames_index()
INDIA_INDEX = _load_india_index()

# KDTree for fast reverse geocoding (coords -> nearest place). Built once
# at startup since these datasets don't change at runtime.
_india_coords = np.array([[p["lat"], p["lng"]] for p in INDIA_INDEX])
INDIA_TREE = cKDTree(_india_coords)

_geonames_coords = np.array([[p["lat"], p["lng"]] for p in GEONAMES_INDEX])
GEONAMES_TREE = cKDTree(_geonames_coords)

# Rough India bounding box — used to decide which dataset to search first
INDIA_BOUNDS = {"lat_min": 6.0, "lat_max": 37.5, "lng_min": 68.0, "lng_max": 97.5}


def _in_india(lat, lng):
    return (INDIA_BOUNDS["lat_min"] <= lat <= INDIA_BOUNDS["lat_max"] and
            INDIA_BOUNDS["lng_min"] <= lng <= INDIA_BOUNDS["lng_max"])


def reverse_geocode_one(lat, lng):
    if _in_india(lat, lng):
        dist, idx = INDIA_TREE.query([lat, lng])
        return INDIA_INDEX[idx]
    dist, idx = GEONAMES_TREE.query([lat, lng])
    return GEONAMES_INDEX[idx]


# Combined index for forward text search (place name -> coords) — India's
# granular dataset first (more results, more useful), GeoNames after for
# international place names.
PLACE_INDEX = INDIA_INDEX + GEONAMES_INDEX


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


@app.get("/sessions/full")
def list_sessions_full():
    """Fetch all sessions with their full chunk + GPS data in one call —
    used by the map to show every user's recorded path at once."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT session_id, created_at FROM sessions ORDER BY created_at DESC")
    sessions = cur.fetchall()

    result = []
    for s in sessions:
        cur.execute(
            "SELECT chunk_index, video_url, gps_points, created_at FROM chunks "
            "WHERE session_id = %s ORDER BY chunk_index",
            (s["session_id"],),
        )
        chunks = cur.fetchall()
        result.append({
            "session_id": s["session_id"],
            "created_at": s["created_at"],
            "chunks": [
                {
                    "chunk_index": c["chunk_index"],
                    "video_url": c["video_url"],
                    "gps_points": json.loads(c["gps_points"]),
                    "created_at": c["created_at"],
                }
                for c in chunks
            ],
        })

    cur.close()
    conn.close()
    return result


@app.get("/sessions")
def list_sessions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT session_id, created_at FROM sessions ORDER BY created_at DESC")
    sessions = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(s) for s in sessions]


@app.get("/search")
def search_places(q: str, limit: int = 10):
    """Search for a place by name (used by the map's search box). Searches
    the granular India post-office dataset (villages, not just big towns)
    first, then GeoNames for places outside India. Returns coordinates so
    the frontend can pan/zoom the map there."""
    query = q.strip().lower()
    if not query:
        return []

    starts_with = []
    contains = []
    for place in PLACE_INDEX:
        if place["_name_lower"].startswith(query):
            starts_with.append(place)
        elif query in place["_name_lower"]:
            contains.append(place)
        if len(starts_with) >= limit:
            break

    results = (starts_with + contains)[:limit]
    return [
        {
            "name": p["name"],
            "admin1": p["admin1"],
            "admin2": p["admin2"],
            "country_code": p["cc"],
            "lat": p["lat"],
            "lng": p["lng"],
        }
        for p in results
    ]


@app.get("/geocode")
def geocode_point(lat: float, lng: float):
    result = reverse_geocode_one(lat, lng)
    return {
        "name": result["name"],
        "admin1": result["admin1"],
        "admin2": result["admin2"],
        "country_code": result["cc"],
    }


@app.post("/geocode/batch")
def geocode_batch(points: list[dict]):
    if not points:
        return []
    results = [reverse_geocode_one(p["lat"], p["lng"]) for p in points]
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
