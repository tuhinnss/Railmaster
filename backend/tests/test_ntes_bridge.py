from datetime import date, datetime

from app.models.block import BlockOpportunity
from app.ntes_bridge import _block_falls_in_window, apply_ntes_predictions, fetch_predicted_windows


def make_block(**overrides) -> BlockOpportunity:
    defaults = dict(
        block_id="BLK-GHY-LMG-0001",
        section="GHY-LMG",
        start_time=datetime(2026, 9, 28, 2, 0),
        end_time=datetime(2026, 9, 28, 5, 0),
        duration_min=180,
        block_type_possible="traffic",
        expected_train_impact=0.5,  # synthetic placeholder, should get overwritten
        goods_traffic_load=0.2,
    )
    defaults.update(overrides)
    return BlockOpportunity(**defaults)


def test_fetch_predicted_windows_returns_empty_list_when_adapter_unreachable():
    # Port 1 is a reserved/unlikely-bound port; this should fail fast and
    # fall back to [] rather than raising or hanging the caller.
    result = fetch_predicted_windows("GHY-LMG", base_url="http://127.0.0.1:1")
    assert result == []


def test_block_falls_in_window_simple_range():
    block = make_block(start_time=datetime(2026, 9, 28, 2, 30))
    assert _block_falls_in_window(block, "01:00-05:00")
    assert not _block_falls_in_window(block, "06:00-08:00")


def test_block_falls_in_window_crossing_midnight():
    block = make_block(start_time=datetime(2026, 9, 28, 23, 30))
    assert _block_falls_in_window(block, "22:00-02:00")
    block_after_midnight = make_block(start_time=datetime(2026, 9, 28, 0, 30))
    assert _block_falls_in_window(block_after_midnight, "22:00-02:00")


def test_apply_ntes_predictions_overwrites_impact_for_integrated_section(monkeypatch):
    def fake_fetch(corridor, base_url):
        if corridor == "GHY-LMG":
            return [{"corridor": "GHY-LMG", "window": "01:00-05:00", "observed_nights": 84,
                      "clear_nights": 77, "predicted_availability": 0.92, "last_updated": str(date.today())}]
        return []

    monkeypatch.setattr("app.ntes_bridge.fetch_predicted_windows", fake_fetch)

    block = make_block(section="GHY-LMG", start_time=datetime(2026, 9, 28, 2, 0))
    result = apply_ntes_predictions([block])

    assert result[0].expected_train_impact == 0.08  # round(1 - 0.92, 3)


def test_apply_ntes_predictions_leaves_non_integrated_sections_untouched(monkeypatch):
    def fake_fetch(corridor, base_url):
        return [{"corridor": corridor, "window": "01:00-05:00", "observed_nights": 10,
                  "clear_nights": 10, "predicted_availability": 1.0, "last_updated": str(date.today())}]

    monkeypatch.setattr("app.ntes_bridge.fetch_predicted_windows", fake_fetch)

    block = make_block(section="NDLS-GZB", start_time=datetime(2026, 9, 28, 2, 0), expected_train_impact=0.42)
    result = apply_ntes_predictions([block])

    assert result[0].expected_train_impact == 0.42  # untouched -- not an NTES-integrated section


def test_apply_ntes_predictions_falls_back_when_no_predictions_available(monkeypatch):
    monkeypatch.setattr("app.ntes_bridge.fetch_predicted_windows", lambda corridor, base_url: [])

    block = make_block(section="GHY-LMG", expected_train_impact=0.33)
    result = apply_ntes_predictions([block])

    assert result[0].expected_train_impact == 0.33  # untouched -- adapter had nothing to offer


def test_apply_ntes_predictions_leaves_block_untouched_outside_any_predicted_window(monkeypatch):
    def fake_fetch(corridor, base_url):
        return [{"corridor": "GHY-LMG", "window": "01:00-05:00", "observed_nights": 10,
                  "clear_nights": 9, "predicted_availability": 0.9, "last_updated": str(date.today())}]

    monkeypatch.setattr("app.ntes_bridge.fetch_predicted_windows", fake_fetch)

    block = make_block(section="GHY-LMG", start_time=datetime(2026, 9, 28, 12, 0), expected_train_impact=0.5)
    result = apply_ntes_predictions([block])

    assert result[0].expected_train_impact == 0.5  # noon isn't in the 01:00-05:00 window
