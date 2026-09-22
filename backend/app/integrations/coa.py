"""Control Office Application adapter: corridor block availability, train
timetable, and goods forecast. Mocked for now."""

from app.models.corridor import BlockWindow, TrainTimetableEntry, GoodsForecast
from app.mock_data import generators


class COAAdapter:
    def fetch_block_windows(self) -> list[BlockWindow]:
        return generators.generate_block_windows()

    def fetch_timetable(self) -> list[TrainTimetableEntry]:
        return generators.generate_timetable()

    def fetch_goods_forecast(self) -> list[GoodsForecast]:
        return generators.generate_goods_forecast()
