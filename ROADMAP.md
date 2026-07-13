# सफर — Full Roadmap

Every feature/task the project needs, organized by category, with priority
tags so we can work through them one at a time instead of jumping around.

**Priority key:**
- 🔴 P0 — Blocks real-world usage; nothing else matters until these work
- 🟡 P1 — Needed for the product to feel complete and trustworthy
- 🟢 P2 — Growth / polish / nice-to-have, do after P0+P1

Check items off (`[x]`) as they're completed — mirrors the phase tracking
already used in README.md.

---

## 1. Core Recording Experience

- [x] 🔴 **Network-drop resilience** — if a chunk upload fails (common in
      rural areas with patchy signal), queue it locally and retry
      automatically instead of losing it forever
- [ ] 🔴 **Resume an interrupted recording** — if the browser tab closes,
      phone locks, or app crashes mid-walk, don't lose everything recorded
      so far. *(Partially covered by the network-resilience fix above —
      chunks already recorded survive a reload and get uploaded
      automatically. Still missing: resuming the live camera+GPS capture
      itself after a crash, mid-walk.)*
- [ ] 🟡 Pause/resume recording (not just start/stop)
- [ ] 🟡 Live GPS accuracy indicator shown while recording (warn if signal
      is poor, e.g. "GPS weak — video may not line up well")
- [ ] 🟢 Recording quality settings (let the user trade off video quality
      vs data usage)
- [ ] 🟢 Battery/storage warning before starting a long recording

## 2. Playback / "Street View" Experience

- [ ] 🔴 **Continuous auto-advance across chunks** — this is the actual
      core product idea ("chalte hue dekhna"). Right now clicking a point
      plays one 5-second chunk and stops; it should keep playing into the
      next chunk seamlessly, like walking through the video
- [ ] 🟡 Forward/backward buttons to step along the path (real street-view
      style navigation, not just clicking map points)
- [ ] 🟡 A position marker on the map that moves in sync with video
      playback, so you can see where you are on the path as the video plays
- [ ] 🟡 Scrub/seek bar for the whole path (drag to jump anywhere along
      the route, not just chunk-by-chunk)
- [ ] 🟢 Preload the next chunk in the background so playback doesn't
      stutter between chunks
- [ ] 🟢 Playback speed control

## 3. Map & Discovery

- [x] 🟡 Village-level location names (current GeoNames dataset is too
      sparse for rural areas — see README's "Planned" table)
      *(Fixed — now using India Post's post-office directory, 150,000+
      locations, MIT-licensed, bundled in backend/data/india_places.json.gz.
      Also had to fix a memory crash this caused — see 🔴 item below)*
- [x] 🔴 **Backend memory crash (Render OOM)** — loading the new 165K-place
      dataset the naive way (raw JSON with 11 unused columns per row,
      eagerly loading the global GeoNames fallback too) pushed the process
      past Render free tier's 512MB limit, crash-looping the backend.
      Fixed: pre-slimmed the dataset to only the 5 columns actually used,
      switched from dicts to namedtuples (much less per-record overhead),
      dropped the `reverse_geocoder` package dependency (we only needed
      its bundled CSV, now shipped directly), and made the global GeoNames
      fallback lazy — only loaded into memory if someone actually queries
      a point outside India. Idle/common-case memory: ~183MB (was crashing
      past 512MB before).
- [ ] 🟡 Marker clustering when zoomed out (many overlapping points will
      slow the map down as more paths get recorded)
- [ ] 🟡 "Paths near me" using the visitor's own GPS location
- [ ] 🟢 Dedicated page per recorded path (shareable link, not just a map
      popup)
- [ ] 🟢 Filter paths by date / distance / contributor
- [ ] 🟢 Coverage view — which areas have been walked vs still blank

## 4. Data Quality & Trust

- [ ] 🟡 Detect and merge overlapping paths (if 5 people record the same
      lane, show one path, not 5 stacked lines)
- [ ] 🟡 Report/flag inappropriate or wrong content
- [ ] 🟢 Admin moderation view (review flagged content)
- [ ] 🟢 Path descriptions/tags from contributors (e.g. "gets muddy in
      monsoon", "shortcut to the school")
- [ ] 🟢 Edit history for a path (if corrected or re-recorded)

## 5. Contribution & Identity

- [ ] 🟡 Lightweight nickname at recording time (no full login) — enough
      to say "recorded by ___" and start building a contribution history
- [ ] 🟢 "My recordings" page (needs the nickname/identity above)
- [ ] 🟢 Leaderboard — top contributors by distance walked
- [ ] 🟢 Full account system (only if the lightweight version isn't enough)

## 6. Backend & Infrastructure

- [x] 🔴 **Fix backend cold-start** — Render free tier sleeps after 15 min
      idle, causing ~30s delay on the first request. Options: a scheduled
      keep-alive ping, or move to a host without this limitation
      *(stopgap: GitHub Actions pings /health every 10 min — see
      .github/workflows/keep-alive.yml. Real fix if this ever matters for
      production is a paid Render instance, which doesn't spin down at all)*
- [ ] 🟡 Rate limiting / abuse prevention on upload endpoints
- [ ] 🟡 Backup strategy for the Supabase database
- [ ] 🟢 Basic monitoring/alerting (know when the backend is down)
- [ ] 🟢 Pagination for `/sessions/full` — currently loads every recorded
      session at once, which will get slow as data grows

## 7. Design & UX Polish

- [ ] 🟡 Proper loading states (skeleton screens instead of blank/"—")
- [ ] 🟡 First-time user onboarding — briefly explain what the app does
      before asking for camera/location permission
- [ ] 🟢 Installable PWA (feels like a real app, works offline for the
      shell even if recording still needs network)
- [ ] 🟢 Hindi UI toggle (Mukta font already supports Devanagari)
- [ ] 🟢 Accessibility pass (keyboard navigation, screen reader labels)

## 8. Legal & Trust

- [ ] 🟡 Basic privacy notice — recording in public spaces may capture
      other people; users should know this before they start
- [ ] 🟢 Terms of use
- [ ] 🟢 Data takedown process (someone asks to remove a recording of
      themselves/their property)

## 9. Growth

- [ ] 🟢 Share a recorded path (social share link with a preview)
- [ ] 🟢 Invite/referral flow
- [ ] 🟢 Regional community groups (e.g. one district's contributors)

---

## How we'll use this file

Pick one 🔴 item at a time (they block real usage), work it fully, check
it off, commit. Once all 🔴 are done, move to 🟡, then 🟢. Update this file
whenever a new idea comes up — better to log it here than lose track of it
mid-conversation.
