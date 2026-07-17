from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SimClock:
    now: datetime

    @classmethod
    def starting_at(cls, dt: datetime) -> "SimClock":
        return cls(now=dt)

    def advance(self, minutes: int) -> None:
        self.now += timedelta(minutes=minutes)

    def jump_to_dinner(self) -> None:
        self.now = self.now.replace(hour=18, minute=0, second=0, microsecond=0)
