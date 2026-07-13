# सफर (way_to_destination) — Full Roadmap

Users record video while walking, GPS trail auto-syncs with the video, and it
gets plotted on a map — building an organic, crowdsourced "street view" that
grows as more people record.

**See [ROADMAP.md](./ROADMAP.md) for the full prioritized feature list —
work through it one item at a time rather than jumping around.**

## Concept
- No dependency on Google Street View or any proprietary map/imagery product.
- Only a lightweight coastline/continent outline (public domain, Natural Earth
  data) is used as a background reference on the map.
- All roads/paths/videos shown on the map are 100% user-generated.

## Phases

- [x] **Phase 1** — Camera + GPS capture demo (now `record.html`)
      Tests that video recording and GPS trail logging stay in sync.
      Tested successfully on real device — 5-6m GPS accuracy, clean sync.
- [x] **Phase 2** — Chunked upload backend (`backend/main.py`)
      FastAPI server: start a session, upload video chunks + GPS points per
      chunk, retrieve full session data. Deployed on Render, tested live on
      real device — 9 chunks, 47 GPS points, zero failures.
- [x] **Phase 3** — Map viewer (`map.html`)
      Renders a plain coordinate canvas with a lightweight coastline outline
      (self-hosted public-domain GeoJSON in `data/world.geo.json` — no
      Google/OSM tile dependency), draws the recorded GPS path as a polyline,
      and shows a clickable marker per GPS point with chunk info.
- [x] **Phase 4** — Click-to-seek (`map.html` + backend video endpoint)
      Backend serves individual chunk videos (`GET /session/{id}/chunk/{n}/video`).
      Clicking a point on the map loads that point's chunk video and seeks
      to the right moment within it.
- [x] **Phase 5** — Multi-user overlay (`map.html`)
      Map now loads automatically on open — fetches ALL recorded sessions
      via `GET /sessions/full` and draws every path at once, each in a
      distinct color. No more manually pasting a session_id. A "Zoom" box
      still lets you jump to one specific session if needed.

## Tech Stack

**Currently in use:**
| Layer | Tech | Notes |
|---|---|---|
| Recording UI | Vanilla HTML/JS | `record.html` — camera + GPS capture, chunked upload |
| Dashboard/home | Vanilla HTML/JS | `index.html` — live stats, recent recordings, entry point |
| Map viewer | Vanilla HTML/JS + [Leaflet](https://leafletjs.com/) | `map.html` — Leaflet used only as a rendering engine, no Google/Mapbox tiles |
| Base map reference | Self-hosted GeoJSON | `data/world.geo.json` — public-domain coastline outline (not a live tile service) |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) (Python) | `backend/main.py` — session + chunk upload/retrieval endpoints |
| Database | PostgreSQL ([Supabase](https://supabase.com)) | Sessions + chunk metadata (GPS points as JSON), persistent |
| Video storage | Supabase Storage (S3-compatible) | Public bucket `videos/{session_id}/chunk_N.webm`, persistent |
| Reverse geocoding | India Post directory (150K+ villages) + GeoNames fallback | Offline, no external API calls; village-level accuracy for India |
| Video codec | WebM (VP8) via `MediaRecorder` | Captured at 640x480, ~600kbps |
| Backend hosting | [Render](https://render.com) (free tier) | `way-to-destination.onrender.com` — code/compute only now; all data lives in Supabase, so redeploys/spin-downs no longer wipe anything |
| Frontend hosting | GitHub Pages | Auto-deploys from `main` branch |
| Version control | Git + GitHub | `github.com/Satyam-6200/way_to_destination` |

**Planned (future phases):**
| Layer | Tech | Why |
|---|---|---|
| Frontend framework | React | Once UI complexity grows past a few pages |
| Database extension | PostGIS | Proper geospatial queries (nearby paths, coverage area) at scale |
| User-entered location name | Optional text field at recording time | Reverse geocoding is now much better (village-level India dataset) but still won't always match hyper-local names people actually use. Letting the recording user type the real local name would be the most accurate option. |

### Backend environment variables (Render → Settings → Environment)
Required for the backend to start — set these in Render's dashboard, never
commit real values to the repo:
- `DATABASE_URL` — Supabase Postgres connection string (Transaction pooler URI)
- `SUPABASE_URL` — e.g. `https://xxxx.supabase.co`
- `SUPABASE_SERVICE_KEY` — the Supabase **service_role** secret key (not the anon key)

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
- 2026-07-09: Phase 3 map viewer built (map.html). Uses Leaflet purely as a
  rendering library (no Google/Mapbox tile service) — background is a
  self-hosted, public-domain coastline outline. Fetches a session's GPS
  trail from the backend and draws it as a path with clickable points.
- 2026-07-09: Added haversine distance calculation — total path distance
  shown in status bar, cumulative distance shown per point.
- 2026-07-09: Phase 4 — click-to-seek. Backend now serves individual chunk
  video files. Clicking a marker on the map loads and seeks to the right
  moment in that chunk's video, right in the map page.
- 2026-07-09: Fixed git author email so commits count toward GitHub
  contribution graph (was using a placeholder local email before).
- 2026-07-09: Fixed broken chunk video playback — MediaRecorder was being
  used with a timeslice, which produces webm fragments that aren't valid
  standalone files except the first one. Switched to restarting the
  recorder for every chunk, so each chunk is now a complete, playable
  video file on its own.
- 2026-07-09: Fixed a second video bug — Chrome reports Infinity duration
  for MediaRecorder webm files (header doesn't know final length while
  recording), which silently breaks seeking/rendering. Added the standard
  workaround: seek to a huge timestamp first to force Chrome to compute
  the real duration, then seek to the actual target time.
- 2026-07-09: Cut data usage significantly — capture resolution reduced to
  640x480 and bitrate capped at 600kbps. Was ~1.3-1.5 MB per 5s chunk
  (~1 GB/hour) which is unsustainable for users recording on mobile data;
  now roughly 350-400 KB per 5s chunk (~250-300 MB/hour). Quality is still
  fine for the street-view use case (recognizing a path/route), not meant
  to be HD footage.
- 2026-07-09: Added clear error reporting for video load failures (HTTP
  status, decode errors) instead of a misleading "autoplay blocked"
  message — needed to properly diagnose the video playback issue, which
  turned out to be caused by Render's free-tier ephemeral disk wiping
  old session data on every redeploy, not a code bug.
- 2026-07-09: Added offline reverse geocoding using the `reverse_geocoder`
  library (bundled GeoNames cities1000 dataset, ~7.5MB, public domain).
  No external API calls — fully self-hosted like the coastline data.
  New endpoints: `GET /geocode` (single point) and `POST /geocode/batch`
  (multiple points at once). Map now shows place names (village/district/
  state) in the status bar and in each point's popup.
- 2026-07-09: Migrated storage off Render's ephemeral disk. Confirmed via
  Render's own docs that free-tier disk is wiped on every redeploy,
  restart, AND spin-down (15 min idle) — not just deploys, which explained
  the repeated "video not found" issue. Now using Supabase: Postgres for
  session/chunk metadata, Supabase Storage (S3-compatible, public bucket)
  for video files. Render is now compute-only; all data survives restarts.
  Credentials are read from environment variables set in Render's
  dashboard, never committed to the repo.
- 2026-07-10: Phase 5 complete — map now shows every recorded session
  automatically on load (new `GET /sessions/full` backend endpoint), each
  path drawn in a distinct color, no manual session_id pasting needed.
  All 5 originally planned phases are now done.
- 2026-07-10: Replaced the dev-tool "paste a session_id" box with a real
  place search bar (new `GET /search` backend endpoint — forward search,
  name -> coordinates, using the same offline GeoNames dataset already
  used for reverse geocoding). Typing a place name now shows matching
  results with district/state, and selecting one pans/zooms the map there
  — much closer to how an actual end user would explore the map.
- 2026-07-11: Full app redesign — this was still a set of disconnected
  test pages, not a real product. Restructured into: `index.html` (new
  dashboard/home — hero, live stats, recent recordings), `record.html`
  (the old index.html, recording logic unchanged, restyled), `map.html`
  (restyled, functionality unchanged). Added `styles.css` as a shared
  design system + consistent nav bar across all three pages. Design
  direction: grounded in the actual subject (documenting unmapped rural
  paths) rather than generic dashboard/startup look — Yatra One (display)
  + Mukta (body, Devanagari-ready) + JetBrains Mono (data), warm
  indigo/gold/terracotta palette, a hand-drawn trail motif in the hero.
- 2026-07-11: Renamed the app to सफर (Hindi for "journey") — wordmark
  paired with a small winding-road icon in the nav, matching the hero's
  trail motif at a smaller scale. Converted all Hinglish UI copy to plain
  English (the product itself should read in English; Hinglish is just
  how we talk about it in chat). Simplified the home page's nav to just
  the logo, since Record/Explore are already the two big cards on that
  page — having them in the nav too was redundant. Record and Map pages
  keep the full nav so there's still a way back/around.
- 2026-07-11: Switched the whole design system from dark to a warm, muddy
  cream palette (not stark cream — deepened gold/terracotta/green for
  contrast against a dustier off-white). The map canvas itself stays dark
  on purpose (paths glow against it, separate treatment from the page
  chrome around it). Also filled out the Record page, which felt bare —
  added an intro line and a short "before you start" tips card.
- 2026-07-11: Added the full ROADMAP.md with every planned feature,
  prioritized. Started working through it top-down.
- 2026-07-11: Network-drop resilience (first 🔴 item) — chunks are now
  saved to IndexedDB the instant they're recorded, before attempting
  upload. Failed uploads stay queued and retry automatically (on an
  interval, and on the browser's 'online' event), including across page
  reloads — so a dropped connection or a closed tab no longer loses a
  recorded chunk. A small badge shows how many chunks are waiting.
- 2026-07-11: Backend cold-start fix (second 🔴 item) — added a GitHub
  Actions workflow (.github/workflows/keep-alive.yml) that pings /health
  every 10 minutes so Render's free instance never goes idle long enough
  to spin down. This is a stopgap for the free tier, not a permanent fix
  (a paid Render instance is the real fix if it's ever needed).
- 2026-07-11: Fixed the village-level location accuracy problem. Replaced
  GeoNames cities1000 (only ~200 India entries — too sparse for rural
  areas) with India Post's post-office directory (MIT-licensed npm
  package `india-pincode`'s bundled dataset, 150,000+ locations covering
  villages, not just big towns). Bundled locally as
  backend/data/india_places.json.gz, looked up via a KDTree for fast
  reverse geocoding. GeoNames is kept as a fallback for coordinates
  outside India. Confirmed fix: a test point that used to return
  "Bariarpur, Munger" (wrong — nearest known big town, ~15km off) now
  correctly returns a location in Khagaria district.
- 2026-07-13: The village-level dataset from the previous entry crashed the
  backend with OOM errors on Render (512MB free-tier limit) — loading
  165,627 raw JSON rows (11 columns each, only 5 needed) plus eagerly
  loading the global 144K-row GeoNames fallback pushed memory well past
  the limit. Fixed by: pre-slimming the dataset to a 5-column CSV
  (backend/data/india_places_slim.csv.gz), switching from dicts to
  namedtuples for the in-memory index, dropping the `reverse_geocoder`
  package dependency (we only needed its bundled CSV — now shipped
  directly as backend/data/geonames_fallback.csv.gz), and making the
  GeoNames fallback lazy-load only when an out-of-India point is queried.
  Idle memory dropped from crashing past 512MB to ~183MB.
- 2026-07-13: Added "Paths near me" on the map — a 📍 Near Me button gets
  the visitor's own GPS location, drops a "you are here" marker, and
  lists the closest recorded paths sorted by distance (tap one to zoom
  to it). Distance is computed to the nearest point of each path, not
  just its bounding box, for accuracy.
- 2026-07-13: Added marker clustering (Leaflet.markercluster) so the map
  stays readable and performant as more paths get recorded — nearby
  points group into a numbered cluster at low zoom, and split back into
  individual tappable points once zoomed in past level 16. Cluster icons
  restyled to match the app's gold palette instead of the plugin's
  default blue.
