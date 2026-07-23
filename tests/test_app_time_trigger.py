from datetime import datetime

from app import trigger_time_advance
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def test_time_advance_fires_checkin_on_first_entry_into_dinner_window():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_dates: set[str] = set()

    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)

    assert clock.now == datetime(2026, 7, 17, 18, 0)
    assert messages == [("ai", "王伯伯，您吃完晚餐了嗎？")]
    assert asked_dates == {"2026-07-17"}


def test_time_advance_does_not_repeat_checkin_same_day():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_dates: set[str] = set()

    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)
    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)

    assert clock.now == datetime(2026, 7, 17, 18, 30)
    assert len(messages) == 1


def test_time_advance_outside_window_adds_no_message():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 19, 30))
    messages: list[tuple[str, str]] = []
    asked_dates: set[str] = set()

    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)

    assert messages == []
    assert asked_dates == set()
