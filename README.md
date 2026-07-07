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

- [x] **Phase 1** — Camera + GPS capture demo (`phase1-capture-demo.html`)
      Tests that video recording and GPS trail logging stay in sync.
      Open on a phone browser (needs HTTPS or localhost for camera/GPS
      permissions to work), tap Start, walk a bit, tap Stop. Check that GPS
      points logged look reasonable and the video downloads correctly.
- [ ] **Phase 2** — Chunked upload: send video segments + GPS metadata to backend
- [ ] **Phase 3** — Draw a single recorded path on a map (Leaflet + coastline data)
- [ ] **Phase 4** — Click-to-seek: clicking a point on the path jumps video to that timestamp
- [ ] **Phase 5** — Multiple users/paths overlaid on one shared map

## Stack (planned)
- Frontend: React (Phase 1 is plain HTML/JS for quick testing)
- Backend: FastAPI
- Storage: S3-compatible object storage for video chunks, Postgres + PostGIS for metadata
- Map: Leaflet + Natural Earth coastline GeoJSON (no Google/Mapbox dependency)

## Log
- 2026-07-07: Repo initialized, Phase 1 capture demo built.
