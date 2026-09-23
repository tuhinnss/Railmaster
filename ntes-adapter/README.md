# NTES Adapter

A standalone service for Rail Master (SIH26027, Automatic Block Planning
for Indian Railways). It derives, for a handful of real corridors, how
often a given night-time maintenance window has actually been free of
trains, based on real historical running data rather than the nominal
timetable — and exposes that as `predicted_availability` for the
scheduler to consume. Nothing else lives here: no scheduler, no
dashboard, no frontend.

## Investigation findings (read this before trusting anything below)

NTES (enquiry.indianrail.gov.in) has **no public developer API**. This
section documents exactly what was found by inspecting the real site —
its HTML, its linked JavaScript, and one real live request-response
cycle — not by guessing at plausible endpoint names.

**What NTES actually is.** `enquiry.indianrail.gov.in` redirects to
`/mntes`, a legacy server-rendered web app (not a JSON API, not a modern
SPA). Menu actions are real HTML `<form>` submissions to a `q` endpoint
with `opt=`/`subOpt=` query parameters; the server renders a full HTML
page in response. There is a CSRF protection layer: before any form
submit, the app fetches `GET /mntes/GetCSRFToken?t=<timestamp>`, which
returns a session-tied, randomly-named hidden `<input>` field
(e.g. `<input type='hidden' name='6w2zputh3anw...' value='11pw5sjh...'>`)
that gets appended to the form before it submits.

**The query this service uses: "Live Station".** Reachable via the site's
own "Live Station" menu item (`onMainMenu('liveStation','')` in
`mntes.js`), which loads a page containing a form (`frmSTN`) with fields
`jFromStationInput` (format: `"<CODE> - <NAME>"`, exactly as the site's
own `getStnByCode()` builds it), `jToStationInput` (optional), and `nHr`
(a radio button: confirmed choices are **2, 4, or 8** hours — no other
values are offered by the UI). Submitting it POSTs to
`/mntes/q?opt=LiveStation&subOpt=show`.

**Confirmed by an actual live request** (session cookies + a real CSRF
token + a real POST, done once during this investigation, not repeated):
querying `GHY` (Guwahati) returned a real, current server-rendered page —
*"12 Trains departing from/arriving at GHY - GUWAHATI in next 4 Hrs."* —
with a genuine data table per train: train number, name, arrival
time/status/platform, departure time/status/platform, each shown as an
expected time (colored green/red), a status badge (`"On Time"` or a
delay duration like `"01:25 Hrs."`), and the originally scheduled time.
Trains originating at the queried station show `"Source"` instead of an
arrival. **No CAPTCHA was encountered on this specific query path.** A
second live query (`LMG`, Lumding Jn) confirmed the same structure — *"9
Trains departing from/arriving at LMG..."* — matching its own page
header exactly. Both real responses are saved as fixtures in
`tests/fixtures/` and are what `ntes_parser.py` is actually tested
against, not hand-written HTML.

**Station codes are real, from NTES's own data.** The app ships a
324KB `station_data.js` with every station's code and name
(`{"code":"GHY","name":"GUWAHATI"}`, etc.) — this is NTES's own official
list, pulled directly, not guessed. `GHY`, `LMG`, and `RNY` all exist in
it.

**What is NOT verified, and matters:**
- **The corridors are unconfirmed placeholders.** The user's task
  description offered `GHY-LMG, LMG-RNY` as an *example* of the
  placeholder format. The station *codes* are real (confirmed above);
  whether GHY-LMG and LMG-RNY are genuinely adjacent block sections with
  no intervening major junction — which the occupancy-pairing logic in
  `occupancy.py` assumes — has **not** been independently verified
  against real track topology. Confirm before treating this data as
  operationally meaningful. See `app/config.py`.
- **There is no historical archive.** This is the single biggest finding
  and it shapes the whole design: NTES's Live Station board is a
  forward-looking "next N hours" view. There is no discovered way to ask
  it "what happened between these two stations last Tuesday night."
  `predicted_availability` in this service can therefore **only be
  built from data collected going forward** by this service's own
  poller — it cannot be seeded or backfilled with real history on day
  one. A freshly started instance will report `observed_nights: 0` for
  every window until it has actually been running and polling for a
  while. This is expected, not a bug (see `test_frequency.py`).
- **The "Destination" / terminating-train cell format is unconfirmed.**
  The two real captured responses both happened to show every departure
  as a real timed departure — no train example that *terminates* at the
  queried station was observed live. `ntes_parser.py` guesses the
  terminating case mirrors the confirmed "Source" case (a text marker
  instead of a time triplet) and handles it defensively, but this
  specific branch has not been proven against real data. If it's wrong,
  the parser falls back to `TrainEventStatus.UNKNOWN` and drops that one
  event rather than emitting bad data — see `_parse_event_cell` in
  `ntes_parser.py`.
- **Behavior under sustained polling is unknown.** One successful query
  was made per station during investigation, deliberately not repeated,
  per the task's rate-limit instruction. Whether continuous 60-second
  polling triggers a CAPTCHA, a session/IP block, or different behavior
  over time was **not tested** and should not be assumed safe. Treat
  `POLL_INTERVAL_SECONDS` as something to tune conservatively in
  practice, and watch the poller's logs for repeated failures.
- **This is not, and is never claimed to be, an authorized integration.**
  These are undocumented, internal endpoints of a public information
  website, reverse-engineered from its own client-side code. There is no
  API agreement, no rate-limit contract, no stability guarantee. Anyone
  deploying this for real use should get explicit sign-off, not treat
  this README as that sign-off.

## Architecture

```
RailwayDataProvider (interface)
├── MockProvider             — canned, deterministic. Default everywhere, incl. all tests.
├── CapturedFixtureProvider  — replays real captured NTES responses. No network.
└── NTESProvider             — best-effort real scraper. Opt-in only.
        │
        ▼
   Poller (background, on an interval)
        │  fetches both stations of each corridor,
        │  never lets a failure propagate or wipe the cache
        ▼
   Store (live-board cache + occupancy log + poll-coverage log + predictions cache)
        │
   ┌────┴────┐
   ▼         ▼
occupancy.py  frequency.py
(pairs A/B    (clear_nights / observed_nights
 events into   over self-collected data only)
 intervals)
        │
        ▼
   FastAPI (main.py) — 3 read endpoints, all served from the Store
```

## Setup

```bash
cd ntes-adapter
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt                   # macOS/Linux

# Run tests (MockProvider only, no network required)
.venv/Scripts/python.exe -m pytest -q

# Run the service (defaults to MockProvider)
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Environment variables (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `NTES_ADAPTER_PROVIDER` | `mock` | `mock`, `fixture`, or `ntes` — see below. |
| `NTES_ADAPTER_POLL_INTERVAL` | `60` | Seconds between poll cycles. |
| `NTES_ADAPTER_DATA_DIR` | `ntes-adapter/data/` | Where the JSON-file store persists between restarts. |

### Providers

- **`mock`** (default) — canned, deterministic trains (`MOCK EXPRESS`).
  Used by every test. Never present this as real data.
- **`fixture`** — replays the two real NTES responses captured during
  investigation (`tests/fixtures/`), parsed by the same parser used for
  live responses. Real train numbers, names, delays and platforms; no
  network access. The captured HTML carries only `HH:MM` times with no
  date, so times are anchored to today — the train identities and timings
  are real, the calendar date they're shown against is not the date they
  were observed. Only `GHY` and `LMG` were captured; `RNY` raises, so
  `LMG-RNY` honestly reports no data for that end rather than silently
  substituting mock trains.
- **`ntes`** — best-effort live scrape. Read the investigation section
  above first; sustained polling behavior was never tested.

`/live` reports which of these produced the boards in its `provider`
field, so a consumer can never accidentally present canned data as real.

## Demo seeding

A freshly started instance reports `observed_nights: 0` until the poller
has actually run for a while (see investigation findings above — there's
no historical backfill). To get illustrative numbers immediately for a
demo, run before starting the service:

```bash
.venv/Scripts/python.exe -m scripts.seed_demo_predictions
```

This seeds `FREQUENCY_LOOKBACK_NIGHTS` worth of *past-night* poll-coverage
and occupancy history (not the predictions cache directly — the poller
recomputes that from the logs on every cycle, including at startup, so a
directly-seeded cache entry gets overwritten within seconds). The seeded
availability figures (`ILLUSTRATIVE_AVAILABILITY` in the script) are
made up, not measured — labeled as such everywhere they surface.

## Consumers

Rail Master's main scheduler (`../backend/app/ntes_bridge.py`) treats
this service as an optional enrichment layer: for its two NTES-integrated
sections, it overwrites a block opportunity's `expected_train_impact`
with `1 - predicted_availability` for blocks whose time falls in a window
this service has data for. It degrades silently to synthetic data if
this service is unreachable — there's no hard dependency in either
direction.

## Configured corridors (placeholders — confirm before real use)

| Corridor | Station A | Station B |
|---|---|---|
| `GHY-LMG` | GHY — Guwahati | LMG — Lumding Jn |
| `LMG-RNY` | LMG — Lumding Jn | RNY — Rangiya Jn |

Edit `app/config.py` to change these. Station codes are validated against
NTES's real station list at time of writing; real-world section
adjacency is not.

## API

- `GET /api/v1/corridors` — the configured corridors.
- `GET /api/v1/corridors/{corridor}/live` — current NTES-derived status
  for both stations of that corridor, with a `stale` boolean, a
  `provider` field naming the data's origin (`mock` /
  `captured_fixture` / `ntes_live`), and a
  `last_successful_fetch` timestamp. `stale=true` whenever the last
  successful fetch is older than `STALE_THRESHOLD_SECONDS` (default 300s
  — roughly 5 poll intervals) — including if the corridor has never been
  successfully fetched at all, in which case both station boards are
  `null` and `last_successful_fetch` is `null`. NTES being unreachable
  never crashes this endpoint; it just keeps returning the last good
  cache with the flag set.
- `GET /api/v1/corridors/{corridor}/predicted-windows` — cached
  frequency predictions for that corridor, ranked by
  `predicted_availability` descending. Always served from cache, never
  recomputed on request (spec requirement) — the poller recomputes it
  after every poll cycle.

## Formulas

**Section occupancy** (`occupancy.py`): a train occupies the section
between station A and station B from its actual/expected departure at A
to its actual/expected arrival at B (matched by train number, earliest
qualifying arrival after the departure, capped at
`MAX_SECTION_TRANSIT_MINUTES` to avoid mis-pairing an unrelated later
service). Both directions (A→B and B→A) are paired independently and
merged. Timestamps are full datetimes, so a departure just before
midnight and an arrival just after it pair correctly with no special
casing — the arrival simply falls on the next calendar date.

**Frequency prediction** (`frequency.py`):

```
predicted_availability = clear_nights / observed_nights
```

over the last `FREQUENCY_LOOKBACK_NIGHTS` (default 90) *past* nights.
`observed_nights` counts nights where the poller actually had live
coverage during that specific window (at least one successful poll
timestamp landing inside it) — not just any night with no recorded
occupancy, because those aren't the same thing: a night nobody polled
looks identical to a genuinely clear night if you only look at the
occupancy log. This is why the Store tracks poll-coverage timestamps
separately from occupancy intervals. A night is `clear_nights` if no
occupancy interval overlaps the window at all.

**This is a frequency count over self-collected observations, not a
trained model.** There is no ML here, and it shouldn't be described as
such anywhere downstream.

## Known limitations

- No real historical data on day one (see investigation findings).
- **A single simultaneous capture of both stations yields zero section
  occupancy.** The two captured fixtures (GHY and LMG, taken at the same
  moment) share no train numbers at all, so `derive_corridor_occupancy`
  returns nothing for them. This is structural, not a parsing bug: each
  board is a ~4-hour *forward* look, and a train crossing the ~180km
  section appears in one board's window but not the other's. Occupancy
  pairing therefore only produces intervals from data accumulated by
  polling over time — it cannot be reconstructed from a point-in-time
  snapshot of both ends, which is why the `fixture` provider is useful
  for showing real train boards but not for deriving real availability.
- Terminating-train HTML cell format unconfirmed against live data.
- Corridor real-world adjacency unconfirmed.
- Behavior under sustained/high-frequency polling unverified — only one
  live query per station was made during development.
- Single-process, JSON-file persistence — fine for a prototype, not
  built for concurrent writers or high availability.
