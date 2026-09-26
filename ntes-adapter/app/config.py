"""Configured corridors and tunables.

CORRIDORS is a PLACEHOLDER pending confirmation. GHY, LMG, and RNY are
real, valid station codes -- confirmed by pulling NTES's own station
database (see README investigation section). What is NOT independently
verified is that GHY-LMG and LMG-RNY are genuinely adjacent block
sections in the real track topology with no intervening major stations
that would break the two-station pairing assumption in occupancy.py.
Confirm real corridors before treating this data as operationally
meaningful.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Corridor:
    corridor_id: str
    station_a: str
    station_a_name: str
    station_b: str
    station_b_name: str


CORRIDORS: list[Corridor] = [
    Corridor("GHY-LMG", "GHY", "GUWAHATI", "LMG", "LUMDING JN"),
    Corridor("LMG-RNY", "LMG", "LUMDING JN", "RNY", "RANGIYA JN"),
    # High-density: ~25 km on the Delhi-Howrah trunk. Real captures show 64
    # movements at NDLS and 60 at GZB in an 8-hour window, against 23 and 18
    # for the Assam corridors above. Because the section is short, departures
    # from one end and arrivals at the other both land inside a single capture
    # window, so occupancy pairing yields real intervals here -- see README.
    Corridor("NDLS-GZB", "NDLS", "NEW DELHI", "GZB", "GHAZIABAD"),
]

# Recurring night windows to compute frequency predictions for, as
# "HH:MM-HH:MM" strings. Handles windows that cross midnight.
NIGHT_WINDOWS: list[str] = ["01:00-05:00"]

# How far ahead each live-station query looks (NTES offers 2/4/8 hr radio
# options for this query type -- see README).
LIVE_QUERY_WINDOW_HOURS = 4

# Background poller.
POLL_INTERVAL_SECONDS = 60
POLL_MAX_BACKOFF_SECONDS = 600
STALE_THRESHOLD_SECONDS = 300  # ~5x the poll interval

# Booked timetables ("Trains between stations"). A timetable changes at most
# a few times a year, so each corridor is re-fetched about daily: two
# queries per corridor, spaced apart, one corridor per poll cycle, and a
# failed fetch waits before trying again rather than retrying every cycle.
TIMETABLE_MAX_AGE_HOURS = 24
TIMETABLE_RETRY_MINUTES = 60
TIMETABLE_QUERY_GAP_SECONDS = 3

# How many nights of self-collected data to roll into a frequency prediction.
FREQUENCY_LOOKBACK_NIGHTS = 90

# Section-occupancy pairing: reject a departure/arrival match whose gap
# exceeds this (guards against pairing a departure with an unrelated
# arrival of a train that only runs this route occasionally).
MAX_SECTION_TRANSIT_MINUTES = 240
