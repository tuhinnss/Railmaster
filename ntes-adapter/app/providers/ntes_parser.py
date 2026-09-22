"""Parses NTES's server-rendered "Live Station" HTML table into
StationLiveBoard/TrainEvent. Pure functions, no network -- testable
directly against saved fixtures (see tests/fixtures/, captured from real
NTES responses during investigation).

This is scraping an undocumented page, not consuming a JSON API: the
structure below was reverse-engineered from two real captured responses
(GHY and LMG, next-4-hours queries, September 2026) and is liable to
break on any NTES UI change. See README.md for the full investigation
notes, including which parts of this structure (e.g. what a
"Destination" / terminating-train cell looks like) were never actually
observed and are handled defensively rather than confirmed.
"""

import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from app.models import EventType, StationLiveBoard, TrainEvent, TrainEventStatus

_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
_DELAY_RE = re.compile(r"(\d{1,2}):(\d{2})\s*Hrs\.?", re.IGNORECASE)


def _parse_hhmm(text: str, query_time: datetime) -> datetime | None:
    match = _TIME_RE.search(text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    candidate = query_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # The live board only shows a short look-ahead window, so a shown time
    # that lands more than a few hours "before" the query moment almost
    # certainly rolled past midnight into the next calendar day, not that
    # it's hours in the past. Heuristic, not derived from an explicit date
    # field -- NTES's HTML doesn't carry a clean one for each row.
    if candidate < query_time - timedelta(hours=3):
        candidate += timedelta(days=1)
    return candidate


def _parse_event_cell(td) -> dict:
    text_all = td.get_text(" ", strip=True)
    if text_all.lower().startswith("source"):
        return {"marker": "source"}
    if text_all.lower().startswith("destination"):
        return {"marker": "terminating"}

    fonts = td.find_all("font")
    span = td.find("span", class_=re.compile("w3-round"))
    if len(fonts) < 2 or span is None:
        return {"marker": "unknown"}

    expected_str = fonts[0].get_text(strip=True).rstrip("*")
    scheduled_str = fonts[-1].get_text(strip=True)
    status_text = span.get_text(strip=True)

    delay_match = _DELAY_RE.search(status_text)
    if delay_match:
        status = TrainEventStatus.DELAYED
        delay_minutes = int(delay_match.group(1)) * 60 + int(delay_match.group(2))
    else:
        status = TrainEventStatus.ON_TIME
        delay_minutes = 0

    return {
        "marker": None,
        "expected_str": expected_str,
        "scheduled_str": scheduled_str,
        "status": status,
        "delay_minutes": delay_minutes,
    }


def _parse_row(tr, station_code: str, query_time: datetime) -> list[TrainEvent]:
    cells = tr.find_all("td")
    if len(cells) < 5:
        return []

    info_cell = cells[1]
    bolds = info_cell.find_all("b")
    if len(bolds) < 2:
        return []
    train_no = bolds[0].get_text(strip=True)
    train_name = bolds[1].get_text(strip=True)

    platform_bold = cells[4].find("b")
    platform = platform_bold.get_text(strip=True).rstrip("*") if platform_bold else None

    events: list[TrainEvent] = []

    arrival = _parse_event_cell(cells[2])
    if arrival["marker"] is None:
        events.append(
            TrainEvent(
                train_no=train_no,
                train_name=train_name,
                station_code=station_code,
                event_type=EventType.ARRIVAL,
                status=arrival["status"],
                scheduled_time=_parse_hhmm(arrival["scheduled_str"], query_time),
                actual_or_expected_time=_parse_hhmm(arrival["expected_str"], query_time),
                delay_minutes=arrival["delay_minutes"],
                platform=platform,
            )
        )
    elif arrival["marker"] == "source":
        events.append(
            TrainEvent(
                train_no=train_no,
                train_name=train_name,
                station_code=station_code,
                event_type=EventType.ARRIVAL,
                status=TrainEventStatus.SOURCE,
                platform=platform,
            )
        )
    # "unknown" marker (cell format didn't match anything recognized):
    # skip this event defensively rather than emit bad data.

    departure = _parse_event_cell(cells[3])
    if departure["marker"] is None:
        events.append(
            TrainEvent(
                train_no=train_no,
                train_name=train_name,
                station_code=station_code,
                event_type=EventType.DEPARTURE,
                status=departure["status"],
                scheduled_time=_parse_hhmm(departure["scheduled_str"], query_time),
                actual_or_expected_time=_parse_hhmm(departure["expected_str"], query_time),
                delay_minutes=departure["delay_minutes"],
                platform=platform,
            )
        )
    elif departure["marker"] == "terminating":
        events.append(
            TrainEvent(
                train_no=train_no,
                train_name=train_name,
                station_code=station_code,
                event_type=EventType.DEPARTURE,
                status=TrainEventStatus.TERMINATING,
                platform=platform,
            )
        )

    return events


def parse_live_station_html(
    html: str, station_code: str, query_time: datetime, window_hours: int
) -> StationLiveBoard:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="myTable")

    events: list[TrainEvent] = []
    if table is not None:
        for tr in table.find_all("tr"):
            if tr.find("th") is not None:
                continue  # header row
            events.extend(_parse_row(tr, station_code, query_time))

    return StationLiveBoard(
        station_code=station_code,
        fetched_at=query_time,
        window_hours=window_hours,
        events=events,
    )
