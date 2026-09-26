"""Parses NTES's server-rendered "Trains between stations" page into
TimetabledTrain rows. Pure functions, no network -- tested against the
real responses captured on 2026-09-26 (tests/fixtures/
ntes_real_trains_between_*.html: NDLS<->GZB and GHY<->LMG).

Each train is one <td colspan=3> card: number and name, "days | type",
then a flex row whose left and right spans hold "HH:MM", the station
name and the station code at each end. The right-hand code is not always
inside <b> (NTES's markup has a stray </b>), so cells are read as text
lines rather than by tag.

The page states its own count ("160 Trains found from ..."). A parse that
doesn't reach that count raises rather than returning a short list, so a
changed layout shows up as a fetch failure instead of a timetable with
trains silently missing from it.
"""

import re

from bs4 import BeautifulSoup

from app.models import TimetabledTrain

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_COUNT_RE = re.compile(r"(\d+)\s+Trains?\s+found", re.IGNORECASE)
_HHMM_RE = re.compile(r"^\d{1,2}:\d{2}$")


def _running_days(text: str) -> list[str]:
    text = text.strip()
    if text == "Daily":
        return list(WEEKDAYS)
    days = [d.strip() for d in text.split(",")]
    unknown = [d for d in days if d not in WEEKDAYS]
    if unknown:
        # Every value in the captures was "Daily" or a weekday list; anything
        # else is a format never seen, so refuse it rather than guess.
        raise ValueError(f"Unrecognised running days {text!r}")
    return days


def _end(span) -> tuple[str, str]:
    """(HH:MM, station code) from one end of a train card."""
    lines = [line for line in span.get_text("\n", strip=True).split("\n") if line]
    if len(lines) < 3 or not _HHMM_RE.match(lines[0]):
        raise ValueError(f"Unexpected train-card end {lines!r}")
    return lines[0], lines[-1]


def parse_trains_between_html(html: str) -> list[TimetabledTrain]:
    soup = BeautifulSoup(html, "html.parser")
    count = _COUNT_RE.search(soup.get_text(" ", strip=True))
    if count is None:
        raise ValueError("No 'N Trains found' header -- not a Trains-between-stations result page")

    trains: list[TimetabledTrain] = []
    for td in soup.find_all("td", attrs={"colspan": "3"}):
        spans = td.find_all("span", recursive=False)
        flex = td.find("div", style=re.compile(r"display:\s*flex"))
        if len(spans) < 2 or flex is None or spans[0].find("b") is None:
            continue  # not a train card
        number = spans[0].find("b").get_text(strip=True)
        name = spans[0].get_text(" ", strip=True).removeprefix(number).strip()
        days_text, _, train_type = spans[1].get_text(strip=True).partition("|")
        ends = flex.find_all("span", recursive=False)
        if len(ends) < 2:
            raise ValueError(f"Train {number}: expected two ends, found {len(ends)}")
        departs, from_station = _end(ends[0])
        arrives, to_station = _end(ends[-1])
        trains.append(
            TimetabledTrain(
                train_no=number,
                train_name=name,
                train_type=train_type.strip(),
                running_days=_running_days(days_text),
                from_station=from_station,
                departs=departs,
                to_station=to_station,
                arrives=arrives,
            )
        )

    expected = int(count.group(1))
    if len(trains) != expected:
        raise ValueError(f"NTES says {expected} trains but {len(trains)} parsed -- page layout may have changed")
    return trains
