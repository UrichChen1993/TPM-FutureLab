from datetime import datetime

from simulator.clock import SimClock


def test_advance_adds_minutes():
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    clock.advance(30)
    assert clock.now == datetime(2026, 7, 17, 18, 0)


def test_jump_to_dinner_sets_18_00():
    clock = SimClock.starting_at(datetime(2026, 7, 17, 14, 5))
    clock.jump_to_dinner()
    assert clock.now == datetime(2026, 7, 17, 18, 0, 0)
