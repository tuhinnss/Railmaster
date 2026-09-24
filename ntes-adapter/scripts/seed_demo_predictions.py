"""Seeds poll-coverage and occupancy history for the configured
corridors so a natural frequency recompute produces illustrative but
plausible predicted-availability numbers.

Seeding the predictions cache directly doesn't work: the poller
recomputes predictions from the occupancy/coverage logs on every cycle,
including immediately at startup, so a directly-seeded cache entry gets
overwritten within seconds. This seeds the logs themselves instead, for
FREQUENCY_LOOKBACK_NIGHTS worth of *past* nights -- which the live
poller's current-moment activity never touches -- so the numbers survive
restarts and recomputes.

These are NOT real historical observations -- see
ILLUSTRATIVE_AVAILABILITY. Run this before starting the service (or
restart the service afterward so it reloads from disk).
"""

import os
import random
from datetime import date, timedelta
from pathlib import Path

from app.config import CORRIDORS, FREQUENCY_LOOKBACK_NIGHTS, NIGHT_WINDOWS
from app.frequency import parse_window, window_datetimes
from app.models import SectionOccupancyInterval
from app.store import Store

# Illustrative only -- not measured over 90 nights. GHY-LMG assumed
# reliably clear at night (a quieter branch line); LMG-RNY busier/less
# predictable; NDLS-GZB low because it is a high-density trunk section --
# real captures there show ~60 movements per 8-hour window against ~20 on
# the Assam corridors, so night-time clearance is genuinely rare.
ILLUSTRATIVE_AVAILABILITY = {
    "GHY-LMG": 0.92,
    "LMG-RNY": 0.68,
    "NDLS-GZB": 0.24,
}
DEFAULT_AVAILABILITY = 0.75


def seed_store(store: Store, seed: int = 7) -> None:
    rng = random.Random(seed)
    today = date.today()
    window_start, window_end = parse_window(NIGHT_WINDOWS[0])

    for corridor in CORRIDORS:
        availability = ILLUSTRATIVE_AVAILABILITY.get(corridor.corridor_id, DEFAULT_AVAILABILITY)
        for i in range(1, FREQUENCY_LOOKBACK_NIGHTS + 1):
            night = today - timedelta(days=i)
            start_dt, end_dt = window_datetimes(night, window_start, window_end)

            # Poll coverage: pretend we successfully polled partway through the window.
            store.append_poll_success(corridor.corridor_id, start_dt + (end_dt - start_dt) / 2)

            # Occupied on a (1 - availability) fraction of nights.
            if rng.random() >= availability:
                window_minutes = int((end_dt - start_dt).total_seconds() // 60)
                occupied_start = start_dt + timedelta(minutes=rng.randint(0, max(window_minutes - 15, 0)))
                store.append_occupancy(
                    [
                        SectionOccupancyInterval(
                            corridor=corridor.corridor_id,
                            train_no="SEED",
                            occupied_from=occupied_start,
                            occupied_to=occupied_start + timedelta(minutes=15),
                        )
                    ]
                )


if __name__ == "__main__":
    data_dir = Path(os.environ.get("NTES_ADAPTER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
    seed_store(Store(data_dir=data_dir))
    print(
        f"Seeded {FREQUENCY_LOOKBACK_NIGHTS} nights of illustrative history for "
        f"{[c.corridor_id for c in CORRIDORS]} into {data_dir}"
    )
