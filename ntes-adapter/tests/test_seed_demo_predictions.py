from app.config import CORRIDORS, FREQUENCY_LOOKBACK_NIGHTS
from app.frequency import compute_predicted_windows
from app.store import Store
from scripts.seed_demo_predictions import ILLUSTRATIVE_AVAILABILITY, seed_store


def test_seed_produces_availability_close_to_target():
    """Seeded history is randomized, so check it lands within a
    reasonable tolerance of the illustrative target rather than exact --
    exactness would make the test as brittle as the seed's RNG."""
    from datetime import date

    store = Store(data_dir=None)
    seed_store(store, seed=7)

    for corridor in CORRIDORS:
        target = ILLUSTRATIVE_AVAILABILITY[corridor.corridor_id]
        intervals = store.get_occupancy(corridor.corridor_id)
        poll_timestamps = store.get_poll_timestamps(corridor.corridor_id)
        predictions = compute_predicted_windows(
            corridor.corridor_id, ["01:00-05:00"], intervals, poll_timestamps, FREQUENCY_LOOKBACK_NIGHTS, date.today()
        )
        assert predictions[0].observed_nights == FREQUENCY_LOOKBACK_NIGHTS
        assert abs(predictions[0].predicted_availability - target) < 0.1
