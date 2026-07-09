# Crowdsourced Street View Platform

Users record video while walking, GPS trail auto-syncs with the video, and it
gets plotted on a map — building an organic, crowdsourced "street view" that
grows as more people record.

## Concept
- No dependency on Google Street View or any proprietary map/imagery product.
- Only a lightweight coastline/continent outline (public domain, Natural Earth
  data) is used as a background reference on the map.
- All roads/paths/videos shown on the map are 100% user-generated.

## Phases

- [x] **Phase 1** — Camera + GPS capture demo (`index.html`)
      Tests that video recording and GPS trail logging stay in sync.
      Tested successfully on real device — 5-6m GPS accuracy, clean sync.
- [x] **Phase 2** — Chunked upload backend (`backend/main.py`)
      FastAPI server: start a session, upload video chunks + GPS points per
      chunk, retrieve full session data. Deployed on Render, tested live on
      real device — 9 chunks, 47 GPS points, zero failures.
- [ ] **Phase 3** — Draw a single recorded path on a map (Leaflet + coastline data)
- [ ] **Phase 4** — Click-to-seek: clicking a point on the path jumps video to that timestamp
- [ ] **Phase 5** — Multiple users/paths overlaid on one shared map

## Stack (planned)
- Frontend: React (Phase 1 is plain HTML/JS for quick testing)
- Backend: FastAPI
- Storage: S3-compatible object storage for video chunks, Postgres + PostGIS for metadata
- Map: Leaflet + Natural Earth coastline GeoJSON (no Google/Mapbox dependency)

## Backend (Phase 2)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Endpoints:
- `POST /session/start` — start a new recording session, returns `session_id`
- `POST /session/{session_id}/chunk` — upload a video chunk + its GPS points
- `GET /session/{session_id}` — fetch all chunks + GPS trail for a session
- `GET /sessions` — list all sessions

## Log
- 2026-07-07: Repo initialized, Phase 1 capture demo built.
- 2026-07-08: Pushed to GitHub, deployed via GitHub Pages, renamed to
  index.html so it loads as the homepage.
- 2026-07-08: Phase 1 tested successfully on real device (Xiaomi/Redmi phone,
  Chrome). Camera + GPS sync confirmed working — 9 GPS points captured over
  ~12 seconds, 5-6m accuracy, video recorded cleanly (3.6 MB). Core capture
  logic validated. Ready to move to Phase 2 (chunked upload to backend).
- 2026-07-08: Phase 2 backend built and tested locally (FastAPI + SQLite).
  Session start, chunked video upload with GPS metadata, and retrieval all
  working. Next: connect frontend to actually upload chunks live, and deploy
  backend somewhere reachable (Render/Railway free tier).
- 2026-07-08: Backend deployed to Render (way-to-destination.onrender.com).
  Frontend updated to upload real chunks every 5s during recording.
  Tested end-to-end on real device: 9 chunks (~1.3-1.5 MB each), 47 GPS
  points, all uploaded successfully with zero failures. Full pipeline
  (camera -> GPS sync -> chunked upload -> backend storage) confirmed
  working live over network. Ready for Phase 3 (map rendering).
